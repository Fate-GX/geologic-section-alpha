"""Launch the source-aware current-plan/terrain preview from the desktop GUI."""
import json
import math
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageDraw
from .section.gsj_transition_review import build_transition_review_template
from .section.mapped_point_evidence import (
    load_gsj_mapped_point_evidence, project_mapped_points_to_geographic_route)
from .section.plan_evidence import lonlat_to_global_pixel
from .section.geographic_linework import (load_geographic_linework_evidence,
    intersect_geographic_linework,add_terrain_elevations)

def attach_mapped_point_evidence(image_path, evidence_path, mapped_point_path,
                                 maximum_display_offset_m):
    """Add provenance-preserving map symbols without authorizing section geometry."""
    evidence = load_gsj_mapped_point_evidence(mapped_point_path)
    plan = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    projected = project_mapped_points_to_geographic_route(
        evidence["features"], plan["routeLonLat"], maximum_display_offset_m)
    visible = [row for row in projected if row["displayState"] == "WithinDisplayBuffer"]
    route = plan["routeLonLat"]
    margin = 0.0015
    bounds = (min(p[0] for p in route)-margin, min(p[1] for p in route)-margin,
              max(p[0] for p in route)+margin, max(p[1] for p in route)+margin)
    left, top = lonlat_to_global_pixel(bounds[0], bounds[3], 15)
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    colors = {"DrillHoleReachedBasement": (170, 0, 210),
              "HotSpring": (0, 170, 255), "Fumarole": (255, 120, 0),
              "ChemicalSampleLocality": (40, 210, 80)}
    for row in visible:
        gx, gy = lonlat_to_global_pixel(row["longitude"], row["latitude"], 15)
        x, y = int(gx-left), int(gy-top)
        color = colors[row["featureKind"]]
        draw.ellipse((x-6, y-6, x+6, y+6), fill=color, outline=(0, 0, 0), width=2)
    image.save(image_path)
    plan["mappedPointEvidence"] = {
        "sourceRecordSha256": evidence["recordSha256"],
        "maximumDisplayOffsetM": float(maximum_display_offset_m),
        "projectedFeatureCount": len(projected),
        "displayedFeatureCount": len(visible),
        "features": projected,
        "authorizationBoundary": "DisplayOnly_NoSubsurfaceSectionConstraint",
    }
    Path(evidence_path).write_text(json.dumps(plan, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    return plan["mappedPointEvidence"]


def attach_mapped_linework_evidence(image_path,evidence_path,linework_path):
    """Draw official surface linework and retain exact route intersections."""
    source=load_geographic_linework_evidence(linework_path)
    plan=json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    intersections=add_terrain_elevations(intersect_geographic_linework(
        plan["routeLonLat"],source["features"]),plan["terrainProfile"])
    route=plan["routeLonLat"];margin=.0015
    bounds=(min(p[0] for p in route)-margin,min(p[1] for p in route)-margin,
            max(p[0] for p in route)+margin,max(p[1] for p in route)+margin)
    left,top=lonlat_to_global_pixel(bounds[0],bounds[3],15)
    _,bottom=lonlat_to_global_pixel(bounds[2],bounds[1],15)
    image=Image.open(image_path).convert("RGB")
    plan_height=min(image.height,max(1,int(math.ceil(bottom-top))))
    plan_image=image.crop((0,0,image.width,plan_height));draw=ImageDraw.Draw(plan_image)
    for feature in source["features"]:
        points=[]
        for lon,lat in feature["verticesLonLat"]:
            gx,gy=lonlat_to_global_pixel(lon,lat,15);points.append((int(gx-left),int(gy-top)))
        draw.line(points,fill=(220,30,30) if feature["kind"]=="Fault" else (0,190,230),
                  width=3 if feature["kind"]=="Fault" else 2)
    for event in intersections["events"]:
        gx,gy=lonlat_to_global_pixel(*event["intersectionLonLat"],15);x,y=int(gx-left),int(gy-top)
        draw.rectangle((x-4,y-4,x+4,y+4),fill=(255,255,255),outline=(0,0,0),width=1)
    image.paste(plan_image,(0,0));image.save(image_path)
    plan["mappedLineworkEvidence"]={"sourceRecordSha256":source["recordSha256"],
      "featureCount":source["featureCount"],"routeIntersections":intersections,
      "authorizationBoundary":"MappedSurfaceIntersectionsOnly_NoSubsurfaceContinuation"}
    Path(evidence_path).write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")
    return plan["mappedLineworkEvidence"]


def execute_plan_preview(project_root, output_parent, route_conditions,
                         mapped_point_path=None, maximum_display_offset_m=500.0,
                         mapped_linework_path=None):
    root = Path(project_root).resolve()
    output = Path(output_parent).resolve() / "current_plan_preview"
    script = root / "research/geologic_dwg_generation/tools/build_gsi_plan_section_demo.py"
    command = [sys.executable, "-B", str(script),
               "--route-json", json.dumps(route_conditions.vertices),
               "--spacing-m", str(route_conditions.sample_spacing_m),
               "--terrain-sampling", route_conditions.terrain_sampling_method,
               "--output", str(output)]
    completed = subprocess.run(command, cwd=root / "subprojects/geologic_3d_engine",
                               text=True, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    image = output / "current_aerial_and_arbitrary_terrain_profile.png"
    evidence = output / "plan_evidence_bundle.json"
    if not image.is_file() or not evidence.is_file():
        raise RuntimeError("平面図プレビュー成果物が生成されませんでした。")
    if mapped_point_path:
        attach_mapped_point_evidence(image, evidence, mapped_point_path,
                                     maximum_display_offset_m)
    if mapped_linework_path:
        attach_mapped_linework_evidence(image,evidence,mapped_linework_path)
    plan=json.loads(evidence.read_text(encoding="utf-8"))
    template=output/"surface_transition_review_template.json"
    template.write_text(json.dumps(build_transition_review_template(plan),ensure_ascii=False,indent=2),encoding="utf-8")
    return image, evidence, template
