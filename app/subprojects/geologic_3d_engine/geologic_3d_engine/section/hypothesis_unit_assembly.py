"""Assemble support-bounded diagnostic lithology polygons from proven boundaries."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def _line(points,name):
    if not isinstance(points,Sequence) or len(points)<2:raise ValueError(f"{name} needs two or more points")
    result=[]
    for point in points:
        if (not isinstance(point,Sequence) or len(point)!=2 or
                any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in point)):
            raise ValueError(f"{name} points must be finite station/elevation pairs")
        result.append([float(point[0]),float(point[1])])
    if any(b[0]<=a[0] for a,b in zip(result,result[1:])):raise ValueError(f"{name} stations must increase")
    return result


def _terrain(profile):
    return _line([[x.get("stationM"),x.get("elevationM")] for x in profile],"terrain")


def _at(line,station):
    if station<line[0][0] or station>line[-1][0]:raise ValueError("station outside boundary")
    if station==line[-1][0]:return line[-1][1]
    for a,b in zip(line,line[1:]):
        if a[0]<=station<=b[0]:
            f=(station-a[0])/(b[0]-a[0]);return a[1]+f*(b[1]-a[1])
    raise AssertionError("covered station not interpolated")


def _area(polygon):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(polygon,polygon[1:]+polygon[:1])))/2


def assemble_hypothesis_lithology_units(terrain_profile, clipping: Mapping,
                                        topology_audit: Mapping, declarations,
                                        *, minimum_thickness_m=1e-6,
                                        allow_empty_diagnostic=False):
    terrain=_terrain(terrain_profile)
    if clipping.get("schemaVersion")!="ContactTerrainClipping-1.0":
        raise ValueError("contact/terrain clipping result is required")
    if topology_audit.get("schemaVersion")!="ContactHypothesisTopologyAudit-1.0":
        raise ValueError("contact topology audit is required")
    if (isinstance(minimum_thickness_m,bool) or not isinstance(minimum_thickness_m,(int,float)) or
            not math.isfinite(minimum_thickness_m) or minimum_thickness_m<=0):
        raise ValueError("minimum thickness must be finite and positive")
    if not isinstance(declarations,Sequence) or isinstance(declarations,(str,bytes)):
        raise ValueError("unit declarations must be an array")
    if not declarations and allow_empty_diagnostic is not True:
        raise ValueError("at least one unit declaration is required")
    contacts={}
    for row in clipping.get("contacts",[]):
        key=row.get("hypothesisId")
        if key in contacts:raise ValueError("contact clipping IDs must be unique")
        contacts[key]=[_line(segment,f"contact {key}") for segment in row.get("nominalSubsurfaceSegments",[])]
    proven={(r.get("aboveHypothesisId"),r.get("belowHypothesisId"))
            for r in topology_audit.get("relations",[])
            if r.get("status")=="OrderProvenWithinDeclaredEnvelope"}
    units=[];ids=set()
    for declaration in declarations:
        required={"unitId","sourceLabel","normalizedLabel","evidenceStatus","topBoundary","bottomBoundary"}
        if not isinstance(declaration,Mapping) or not required.issubset(declaration):
            raise ValueError("unit declaration is incomplete")
        unit_id=declaration["unitId"]
        if not isinstance(unit_id,str) or not unit_id or unit_id in ids:raise ValueError("unit IDs must be unique non-empty strings")
        ids.add(unit_id)
        if declaration["evidenceStatus"] not in {"SyntheticAssumption","EvidenceCandidate"}:
            raise ValueError("unit evidence status is unsupported or prematurely authorized")
        top,bottom=declaration["topBoundary"],declaration["bottomBoundary"]
        if not isinstance(top,Mapping) or not isinstance(bottom,Mapping):raise ValueError("unit boundaries must be objects")
        if top.get("type") not in {"Terrain","Contact"} or bottom.get("type")!="Contact":
            raise ValueError("diagnostic units require terrain/contact or contact/contact bounds")
        bottom_id=bottom.get("hypothesisId");bottom_segments=contacts.get(bottom_id)
        if bottom_segments is None:raise ValueError("bottom contact is missing")
        if top.get("type")=="Terrain":
            top_id="Terrain";pairs=[(terrain,segment) for segment in bottom_segments]
        else:
            top_id=top.get("hypothesisId");top_segments=contacts.get(top_id)
            if top_segments is None:raise ValueError("top contact is missing")
            if (top_id,bottom_id) not in proven:
                raise ValueError("contact/contact unit order is not proven")
            pairs=[(a,b) for a in top_segments for b in bottom_segments]
        components=[]
        for top_line,bottom_line in pairs:
            lo=max(top_line[0][0],bottom_line[0][0]);hi=min(top_line[-1][0],bottom_line[-1][0])
            if lo>=hi:continue
            stations=sorted({lo,hi}|{p[0] for p in top_line if lo<p[0]<hi}|
                            {p[0] for p in bottom_line if lo<p[0]<hi})
            upper=[[s,_at(top_line,s)] for s in stations]
            lower=[[s,_at(bottom_line,s)] for s in stations]
            thickness=[a[1]-b[1] for a,b in zip(upper,lower)]
            # A unit that crops out closes at the terrain/contact intersection,
            # so zero thickness is valid only at a support endpoint.  Negative
            # thickness, an all-zero component, and interior closures remain
            # invalid. Contact/contact units require strict positive thickness.
            surface_closure=(top.get("type")=="Terrain")
            invalid_surface=(min(thickness)<-minimum_thickness_m or
                max(thickness)<minimum_thickness_m or
                any(value<minimum_thickness_m for value in thickness[1:-1]))
            if (invalid_surface if surface_closure else min(thickness)<minimum_thickness_m):
                raise ValueError("unit has zero, negative or sub-tolerance thickness")
            polygon=upper+list(reversed(lower))
            area=_area(polygon)
            if area<=0:raise ValueError("unit polygon has zero area")
            components.append({"stationIntervalM":[lo,hi],"topPolyline":upper,
                "bottomPolyline":lower,"polygonStationElevation":polygon,
                "minimumThicknessM":min(thickness),"maximumThicknessM":max(thickness),
                "areaM2":area,"surfaceClosureAtEndpoint":surface_closure and
                    (thickness[0]<minimum_thickness_m or thickness[-1]<minimum_thickness_m)})
        if not components:raise ValueError("unit boundaries have no shared support")
        units.append({"unitId":unit_id,"sourceLabel":declaration["sourceLabel"],
            "normalizedLabel":declaration["normalizedLabel"],
            "evidenceStatus":declaration["evidenceStatus"],"topBoundaryId":top_id,
            "bottomBoundaryId":bottom_id,"components":components,
            "componentCount":len(components),"sectionGeometryAuthorized":False})
    return {"schemaVersion":"HypothesisLithologyUnitAssembly-1.0","unitCount":len(units),
        "units":units,"minimumThicknessM":float(minimum_thickness_m),
        "assemblyState":"NoDeclarationsDiagnostic" if not units else "DiagnosticUnitsAssembled",
        "realRegionAuthorized":False,
        "authorizationBoundary":"SupportBoundedDiagnosticPolygons_NotRealRegionSection"}
