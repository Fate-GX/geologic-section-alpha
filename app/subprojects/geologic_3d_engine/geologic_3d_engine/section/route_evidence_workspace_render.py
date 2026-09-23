"""Render route evidence without converting observations into geology polygons."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def _verify_workspace(document):
    if (not isinstance(document, dict) or
            document.get("schemaVersion") != "RouteEvidenceWorkspace-1.0"):
        raise ValueError("RouteEvidenceWorkspace-1.0 is required")
    claimed = document.get("recordSha256")
    unsigned = {key:value for key,value in document.items() if key != "recordSha256"}
    actual = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()
    if claimed != actual:
        raise ValueError("route evidence workspace hash mismatch")
    profile = document.get("terrainProfile")
    if not isinstance(profile, list) or len(profile) < 2:
        raise ValueError("terrain profile requires at least two samples")
    stations = np.asarray([row.get("stationM") for row in profile], dtype=float)
    elevation = np.asarray([row.get("elevationM") for row in profile], dtype=float)
    if (not np.isfinite(stations).all() or not np.isfinite(elevation).all() or
            stations[0] != 0 or np.any(np.diff(stations) <= 0)):
        raise ValueError("terrain samples must be finite and strictly ordered")
    return stations, elevation


def _color(label):
    digest = hashlib.sha256(str(label).encode("utf-8")).digest()
    return tuple(85 + value % 145 for value in digest[:3])


def render_route_evidence_workspace(workspace_path, image_path, *, width=1400,
                                    height=800, contact_uncertainty_path=None,
                                    morphology_intervals_path=None):
    if (isinstance(width, bool) or isinstance(height, bool) or
            not isinstance(width, int) or not isinstance(height, int) or
            width < 640 or height < 480):
        raise ValueError("render size must be integer pixels of at least 640 by 480")
    source = Path(workspace_path); document=json.loads(source.read_text(encoding="utf-8"))
    stations, terrain = _verify_workspace(document)
    holes = document.get("boreholes", [])
    observations = document.get("structuralObservations", [])
    all_depth_elevations = []
    for hole in holes:
        if isinstance(hole, dict) and isinstance(hole.get("collarElevationM"),(int,float)):
            all_depth_elevations.extend(float(row["bottomElevationM"])
                for row in hole.get("intervals", []) if isinstance(row,dict) and
                isinstance(row.get("bottomElevationM"),(int,float)))
    z_top = max(float(np.max(terrain)), *(all_depth_elevations or [float(np.max(terrain))])) + 35
    z_bottom = min(float(np.min(terrain)), *(all_depth_elevations or [float(np.min(terrain))])) - 60
    left,right,top,bottom=85,width-35,55,height-70
    route_length=float(stations[-1])
    def sx(value):return left+(right-left)*float(value)/route_length
    def sy(value):return top+(bottom-top)*(z_top-float(value))/(z_top-z_bottom)
    image=Image.new("RGB",(width,height),(250,250,250));draw=ImageDraw.Draw(image)
    terrain_pixels=[(round(sx(s)),round(sy(z))) for s,z in zip(stations,terrain)]
    unknown=[(left,bottom),*terrain_pixels,(right,bottom)]
    draw.polygon(unknown,fill=(218,218,218))
    for y in range(top,bottom,14):
        draw.line((left,y,right,y),fill=(232,232,232),width=1)
    draw.line(terrain_pixels,fill=(25,70,30),width=3)
    geology=document.get("surfaceGeology") or {}
    for interval in geology.get("mappedUnitIntervals", []):
        x0,x1=sx(interval["startStationM"]),sx(interval["endStationM"])
        symbol=interval.get("symbol")
        draw.rectangle((x0,top+2,x1,top+17),fill=_color(symbol) if symbol else (235,235,235))
        if symbol:draw.text((x0+2,top+2),str(symbol),fill=(0,0,0))
    for transition in geology.get("transitions", []):
        x0,x1=sx(transition["lowerStationM"]),sx(transition["upperStationM"])
        draw.rectangle((x0,top,x1,bottom),outline=(220,145,20),width=1)
    rendered_contact_uncertainty=[]
    if contact_uncertainty_path is not None:
        uncertainty=json.loads(Path(contact_uncertainty_path).read_text(encoding="utf-8"))
        uncertainty_route_length=float(uncertainty.get("routeLengthM",-1))
        route_length_delta=abs(uncertainty_route_length-route_length)
        # Independent geodesic implementations may differ by centimetres.  This
        # tolerance is only a route-binding check, never a contact uncertainty.
        route_binding_tolerance=max(0.05,route_length*1e-5)
        if (uncertainty.get("schemaVersion") != "MappedContactPositionUncertainty-1.0" or
                route_length_delta > route_binding_tolerance):
            raise ValueError("mapped-contact uncertainty does not match this route")
        boundaries=uncertainty.get("boundaries")
        if not isinstance(boundaries,list) or uncertainty.get("boundaryCount") != len(boundaries):
            raise ValueError("mapped-contact uncertainty boundary count is invalid")
        for boundary_index,row in enumerate(boundaries):
            center=float(row["centerStationM"]);method=row.get("method")
            if row.get("evidenceEligibleNumericZone") is True:
                x0,x1=sx(row["lowerStationM"]),sx(row["upperStationM"])
                draw.rectangle((x0,top,x1,bottom),fill=(245,224,176),outline=(190,115,0),width=1)
                role="EvidenceBoundNumericZone"
            elif method == "MapScaleOnly":
                x=round(sx(center))
                for y in range(top,bottom,12):draw.line((x,y,x,min(y+6,bottom)),fill=(180,70,0),width=2)
                label=f"C{boundary_index+1}?"
                label_x=max(left,min(x-10,right-28))
                draw.text((label_x,top+20+(boundary_index%3)*13),label,fill=(150,55,0))
                role="ExactComputedCrossing_NumericWidthIndeterminate"
            else:
                x0,x1=sx(row["lowerStationM"]),sx(row["upperStationM"])
                draw.rectangle((x0,top,x1,bottom),outline=(135,60,170),width=1)
                role="SyntheticDisplayZone_NotEvidence"
            rendered_contact_uncertainty.append({"transitionId":row.get("transitionId"),
                "centerStationM":center,"renderRole":role})
    rendered_morphology=[]
    if morphology_intervals_path is not None:
        morphology=json.loads(Path(morphology_intervals_path).read_text(encoding="utf-8"))
        delta=abs(float(morphology.get("routeLengthM",-1))-route_length)
        if (morphology.get("schemaVersion") != "ClosedMorphologyRouteIntervals-1.0" or
                delta > max(.05,route_length*1e-5)):
            raise ValueError("morphology intervals do not match this route")
        rows=morphology.get("intervals")
        if not isinstance(rows,list) or morphology.get("intervalCount") != len(rows):
            raise ValueError("morphology interval count is invalid")
        for row in rows:
            start,end=float(row["startStationM"]),float(row["endStationM"])
            selected=[(start,float(np.interp(start,stations,terrain))),
              *((float(s),float(z)) for s,z in zip(stations,terrain) if start<s<end),
              (end,float(np.interp(end,stations,terrain)))]
            draw.line([(round(sx(s)),round(sy(z))) for s,z in selected],fill=(115,35,145),width=6)
            draw.text((max(left,min(sx(start)+4,right-160)),top+58),"mapped crater perimeter interval",fill=(100,20,130))
            rendered_morphology.append({"intervalId":row.get("intervalId"),"startStationM":start,
              "endStationM":end,"renderRole":"MappedSurfaceCraterInterval_NoSubsurfaceInference"})
    rendered_holes=[]
    for hole in holes:
        station=hole.get("stationM")
        if not isinstance(station,(int,float)) or not math.isfinite(station):continue
        x=sx(station);authorized=hole.get("elevationConstraintAuthorized") is True
        for interval in hole.get("intervals", []):
            y0,y1=sy(interval["topElevationM"]),sy(interval["bottomElevationM"])
            draw.rectangle((x-8,y0,x+8,y1),fill=_color(interval.get("normalizedLithology")),
                           outline=(0,0,0) if authorized else (190,25,25),width=2)
        label=f"{hole.get('boreholeId','HOLE')} " + ("Z verified" if authorized else "REPORTED Z / NOT CONSTRAINT")
        draw.text((min(x+11,right-220),max(top+21,sy(hole["collarElevationM"])-12)),label,
                  fill=(0,0,0) if authorized else (180,0,0))
        rendered_holes.append({"boreholeId":hole.get("boreholeId"),"stationM":float(station),
          "absoluteElevationAuthorized":authorized,"renderRole":
          "DirectConstraint" if authorized else "ReportedElevationContextOnly"})
    rendered_observations=[]
    for row in observations:
        if row.get("projectionState") != "Projected":continue
        station=float(row["stationM"]);z=float(np.interp(station,stations,terrain));x,y=sx(station),sy(z)
        angle=math.radians(float(row["apparentDipDegrees"]));length=28
        draw.line((x-length*math.cos(angle),y+length*math.sin(angle),
                   x+length*math.cos(angle),y-length*math.sin(angle)),fill=(35,50,170),width=3)
        rendered_observations.append({"observationId":row.get("observationId"),
          "stationM":station,"renderRole":"ObservedApparentDipSymbol_NotInterpolatedSurface"})
    draw.rectangle((left,top,right,bottom),outline=(0,0,0),width=1)
    draw.text((left,15),"ROUTE EVIDENCE SECTION / GREY = UNKNOWN SUBSURFACE",fill=(0,0,0))
    draw.text((left,bottom+14),
      "Mapped geology is surface context only. Borehole sticks do not imply lateral continuation.",fill=(150,0,0))
    if rendered_contact_uncertainty:
        draw.text((left,bottom+30),
          "C#? dashed orange: computed map crossing; numeric ground-distance accuracy is not declared.",
          fill=(150,55,0))
    target=Path(image_path);target.parent.mkdir(parents=True,exist_ok=True);image.save(target)
    result={"schemaVersion":"RouteEvidenceWorkspaceRender-1.0",
      "workspaceSha256":document["recordSha256"],"imagePath":str(target),
      "imageSha256":hashlib.sha256(target.read_bytes()).hexdigest(),
      "routeLengthM":route_length,"verticalRangeM":[z_bottom,z_top],
      "mappedSurfaceTransitionCount":len(geology.get("transitions",[])),
      "renderedContactPositionUncertainty":rendered_contact_uncertainty,
      "renderedSurfaceMorphologyIntervals":rendered_morphology,
      "contactUncertaintyRouteLengthDeltaM":(route_length_delta if contact_uncertainty_path is not None else None),
      "contactPositionLegend":("Dashed orange = exact computed map crossing; '?' means "
        "the source declares no numeric ground-distance accuracy. Filled orange = evidence-bound zone."),
      "renderedBoreholes":rendered_holes,"renderedStructuralObservations":rendered_observations,
      "subsurfaceFill":"Unknown","lateralInterpolation":"None",
      "authorizationState":"DiagnosticEvidenceOverlay_NotLithologySectionGeometry"}
    return result
