"""Evaluate edited contact hypotheses and render a diagnostic section preview."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .section.contact_orientation_hypothesis import (audit_contact_hypothesis_topology,
    evaluate_contact_orientation_hypotheses)
from .section.contact_terrain_clipping import clip_contact_hypotheses_below_terrain
from .section.hypothesis_unit_assembly import assemble_hypothesis_lithology_units


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def _segment_azimuth(route, index):
    if not isinstance(index, int) or index < 0 or index >= len(route)-1:
        raise ValueError("contact route segment index is invalid")
    a,b=route[index],route[index+1]
    lat=math.radians((float(a[1])+float(b[1]))/2)
    east=(float(b[0])-float(a[0]))*math.cos(lat)
    north=float(b[1])-float(a[1])
    if east==0 and north==0:raise ValueError("route contains a zero-length segment")
    return math.degrees(math.atan2(east,north))%360.0


def _render(plan, clipping, assembly, target):
    terrain=plan["terrainProfile"]
    width,height=1400,780;left,right,top,bottom=95,40,80,90
    stations=[float(x["stationM"]) for x in terrain]
    elevations=[float(x["elevationM"]) for x in terrain]
    for contact in clipping["contacts"]:
        for sample in contact["samples"]:
            elevations.extend([sample["minimumContactElevationM"],sample["maximumContactElevationM"]])
    s0,s1=min(stations),max(stations);z0,z1=min(elevations),max(elevations)
    margin=max(10.0,(z1-z0)*.08);z0-=margin;z1+=margin
    def xy(s,z):
        return (left+(s-s0)/(s1-s0)*(width-left-right),
                top+(z1-z)/(z1-z0)*(height-top-bottom))
    image=Image.new("RGB",(width,height),"white");draw=ImageDraw.Draw(image)
    draw.rectangle((left,top,width-right,height-bottom),outline="#777777")
    draw.line([xy(s,z) for s,z in zip(stations,elevations[:len(stations)])],fill="#315b2f",width=4)
    fill_colors=("#f0d59c","#cdb6a0","#b7d2d8","#d7c4e8")
    for i,unit in enumerate(assembly.get("units",[])):
        for component in unit["components"]:
            draw.polygon([xy(s,z) for s,z in component["polygonStationElevation"]],
                         fill=fill_colors[i%len(fill_colors)],outline="#555555")
    colors=("#b1442e","#3767a8","#8752a1","#aa7b16")
    for i,contact in enumerate(clipping["contacts"]):
        color=colors[i%len(colors)]
        samples=contact["samples"]
        upper=[xy(r["stationM"],r["maximumContactElevationM"]) for r in samples]
        lower=[xy(r["stationM"],r["minimumContactElevationM"]) for r in reversed(samples)]
        if upper and lower:draw.polygon(upper+lower,fill="#eee7df")
        for segment in contact["nominalSubsurfaceSegments"]:
            points=[xy(s,z) for s,z in segment]
            for a,b in zip(points,points[1:]):
                draw.line((a,b),fill=color,width=3)
    font=ImageFont.load_default()
    draw.text((left,25),"CONTACT ORIENTATION DIAGNOSTIC PREVIEW",fill="black",font=font)
    draw.text((left,45),"SYNTHETIC / EVIDENCE CANDIDATE - NOT AUTHORIZED AS A GEOLOGIC SECTION",fill="#a52a2a",font=font)
    if not clipping["contacts"]:
        draw.text((left+30,top+40),"No orientation inputs: terrain only; no subsurface contact generated.",fill="#a52a2a",font=font)
    draw.text((left,height-55),"Station (m)",fill="black",font=font)
    draw.text((width-430,height-55),f"Evaluated contacts: {len(clipping['contacts'])}; diagnostic lithology units: {assembly['unitCount']}",fill="black",font=font)
    target.parent.mkdir(parents=True,exist_ok=True);image.save(target)


def execute_contact_hypothesis_preview(plan_path, intersections_path, template_path, output_parent,
                                       declarations_path=None):
    plan_path=Path(plan_path).resolve();intersection_path=Path(intersections_path).resolve()
    template_path=Path(template_path).resolve()
    plan=json.loads(plan_path.read_text(encoding="utf-8"))
    intersections=json.loads(intersection_path.read_text(encoding="utf-8"))
    template=json.loads(template_path.read_text(encoding="utf-8"))
    if hashlib.sha256(plan_path.read_bytes()).hexdigest()!=intersections.get("planEvidenceSha256"):
        raise ValueError("plan evidence is not the artifact bound to the intersections")
    if template.get("intersectionEvidenceSha256")!=intersections.get("recordSha256"):
        raise ValueError("orientation template is not bound to the intersections")
    route=plan.get("routeLonLat")
    if not isinstance(route,list) or len(route)<2:raise ValueError("plan route is invalid")
    azimuths={row["eventIndex"]:_segment_azimuth(route,row.get("routeSegmentIndex"))
              for row in template.get("hypotheses",[]) if row.get("orientationBasis")!="NeedsInput"}
    evaluation=evaluate_contact_orientation_hypotheses(template,azimuths)
    clipping=clip_contact_hypotheses_below_terrain(evaluation,plan.get("terrainProfile"))
    declarations=[]
    if declarations_path:
        declaration_file=Path(declarations_path).resolve()
        declaration_document=json.loads(declaration_file.read_text(encoding="utf-8"))
        unsigned={k:v for k,v in declaration_document.items() if k!="recordSha256"}
        expected=hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        if declaration_document.get("schemaVersion")!="HypothesisLithologyUnitDeclarations-1.0" or declaration_document.get("recordSha256")!=expected:
            raise ValueError("lithology unit declarations are invalid or hash-mismatched")
        if declaration_document.get("orientationTemplateSha256")!=template.get("recordSha256"):
            raise ValueError("lithology declarations are not bound to the orientation template")
        declarations=declaration_document.get("declarations",[])
    relations=[]
    for declaration in declarations:
        top=declaration.get("topBoundary",{});bottom=declaration.get("bottomBoundary",{})
        if top.get("type")=="Contact" and bottom.get("type")=="Contact":
            relations.append({"aboveHypothesisId":top.get("hypothesisId"),
                "belowHypothesisId":bottom.get("hypothesisId"),"minimumSeparationM":0.0})
    topology=audit_contact_hypothesis_topology(evaluation,relations)
    assembly=assemble_hypothesis_lithology_units(plan.get("terrainProfile"),clipping,topology,
        declarations,allow_empty_diagnostic=not declarations)
    output=Path(output_parent).resolve()/"contact_hypothesis_preview";output.mkdir(parents=True,exist_ok=True)
    evaluation_path=output/"contact_orientation_evaluation.json"
    clipping_path=output/"contact_terrain_clipping.json"
    topology_path=output/"contact_topology_audit.json"
    assembly_path=output/"diagnostic_lithology_unit_assembly.json"
    image_path=output/"contact_hypothesis_preview.png"
    _write_json(evaluation_path,evaluation);_write_json(clipping_path,clipping)
    _write_json(topology_path,topology);_write_json(assembly_path,assembly)
    _render(plan,clipping,assembly,image_path)
    report={"schemaVersion":"ContactHypothesisDiagnosticPreview-1.0",
        "planEvidenceSha256":hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "intersectionEvidenceSha256":intersections["recordSha256"],
        "templateSha256":hashlib.sha256(template_path.read_bytes()).hexdigest(),
        "evaluatedContactCount":evaluation["evaluatedCount"],
        "diagnosticLithologyUnitCount":assembly["unitCount"],
        "drawnLithologyPolygonCount":sum(u["componentCount"] for u in assembly["units"]),
        "realRegionAuthorized":False,
        "authorizationBoundary":"DiagnosticContactCandidatesOnly_NoLithologySectionAuthorization"}
    report_path=output/"contact_hypothesis_preview_report.json";_write_json(report_path,report)
    return report,image_path,report_path,evaluation_path,clipping_path,topology_path,assembly_path
