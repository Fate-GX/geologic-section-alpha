"""Intersect source-linked geographic contact/fault lines with a bent route."""
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping,Sequence
import numpy as np
from .map_template import MeasuredRoute2D

def load_geographic_linework_evidence(path):
    payload=json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schemaVersion")!="GeographicLineworkEvidence-1.0":
        raise ValueError("unsupported geographic linework evidence schema")
    claimed=payload.get("recordSha256")
    unsigned={key:value for key,value in payload.items() if key!="recordSha256"}
    actual=hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()
    if claimed!=actual:raise ValueError("geographic linework evidence hash mismatch")
    features=payload.get("features")
    if not isinstance(features,list) or payload.get("featureCount")!=len(features):
        raise ValueError("geographic linework feature count mismatch")
    if len({row.get("featureId") for row in features})!=len(features):
        raise ValueError("geographic linework feature IDs must be unique")
    return payload

def _metric(route):
    lat0=sum(float(p[1]) for p in route)/len(route)
    sx=6378137*math.cos(math.radians(lat0))*math.pi/180;sy=6378137*math.pi/180
    return [[float(p[0])*sx,float(p[1])*sy] for p in route],sx,sy

def _cross(a,b):return a[0]*b[1]-a[1]*b[0]

def intersect_geographic_linework(route,features,tolerance_m=.01,*,allowed_kinds=None,
                                  interpretation_state=None):
    if not isinstance(route,Sequence) or len(route)<2:raise ValueError("route requires at least two vertices")
    if not isinstance(tolerance_m,(int,float)) or isinstance(tolerance_m,bool) or tolerance_m<=0:raise ValueError("positive tolerance is required")
    allowed={"Contact","Fault"} if allowed_kinds is None else set(allowed_kinds)
    if not allowed or not all(isinstance(value,str) and value for value in allowed):
        raise ValueError("allowed linework kinds are invalid")
    route_xy,sx,sy=_metric(route);measured=MeasuredRoute2D(route_xy);events=[];ambiguities=[]
    required={"featureId","kind","verticesLonLat","sourceId","sourceUrl","locationMethod","locationalConfidence"}
    for feature in features:
        if not isinstance(feature,Mapping) or not required.issubset(feature):raise ValueError("linework feature is incomplete")
        if feature["kind"] not in allowed:raise ValueError("linework kind is not allowed for this intake")
        vertices=feature["verticesLonLat"]
        if not isinstance(vertices,Sequence) or len(vertices)<2:raise ValueError("linework requires two or more vertices")
        if not all(isinstance(feature[k],str) and feature[k].strip() for k in required-{"verticesLonLat"}):raise ValueError("linework identity and provenance are required")
        line=[]
        for point in vertices:
            if not isinstance(point,Sequence) or len(point)!=2 or not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in point):raise ValueError("linework coordinates are invalid")
            if not -180<=point[0]<=180 or not -90<=point[1]<=90:raise ValueError("linework longitude/latitude are invalid")
            line.append(np.array([point[0]*sx,point[1]*sy],float))
        if any(np.linalg.norm(b-a)==0 for a,b in zip(line[:-1],line[1:])):raise ValueError("linework contains a zero-length segment")
        for ri,(a,b) in enumerate(zip(measured.vertices[:-1],measured.vertices[1:])):
            r=b-a
            for fi,(c,d) in enumerate(zip(line[:-1],line[1:])):
                q=d-c;den=_cross(r,q);delta=c-a
                if abs(den)<=tolerance_m*tolerance_m:
                    if abs(_cross(delta,r))<=tolerance_m*np.linalg.norm(r):
                        ambiguities.append({"featureId":feature["featureId"],"kind":feature["kind"],
                          "routeSegmentIndex":ri,"featureSegmentIndex":fi,"classification":"CollinearOverlap_NotPointEvent",
                          "sourceId":feature["sourceId"]})
                    continue
                t=_cross(delta,q)/den;u=_cross(delta,r)/den
                if -1e-12<=t<=1+1e-12 and -1e-12<=u<=1+1e-12:
                    station=float(measured.stations[ri]+min(max(t,0),1)*measured.segment_lengths[ri]);point=a+min(max(t,0),1)*r
                    if any(v["featureId"]==feature["featureId"] and abs(v["stationM"]-station)<=tolerance_m for v in events):continue
                    event={"featureId":feature["featureId"],"kind":feature["kind"],"stationM":station,
                      "routeSegmentIndex":ri,"featureSegmentIndex":fi,"intersectionLonLat":[float(point[0]/sx),float(point[1]/sy)],
                      "sourceId":feature["sourceId"],"sourceUrl":feature["sourceUrl"],"locationMethod":feature["locationMethod"],
                      "locationalConfidence":feature["locationalConfidence"]}
                    for optional in ("unitPair","contactIndex","faultType","dipDegrees","dipDirectionDegrees",
                                     "sourceLabel","sourceLabelEnglish","sourceMajorCode",
                                     "sourceLayer","sourceFeatureId","closedMappedLine"):
                        if optional in feature:event[optional]=feature[optional]
                    events.append(event)
    return {"schemaVersion":"GeographicLineworkIntersections-1.0","routeLengthM":measured.length,
      "events":sorted(events,key=lambda v:(v["stationM"],v["featureId"])),"ambiguities":ambiguities,
      "interpretationState":interpretation_state or "ObservedMapIntersections_NoSubsurfaceContinuation"}

def add_terrain_elevations(intersections,terrain_profile):
    stations=np.asarray([v["stationM"] for v in terrain_profile],float);z=np.asarray([v["elevationM"] for v in terrain_profile],float)
    if len(stations)<2 or not np.isfinite(z).all() or np.any(np.diff(stations)<=0):raise ValueError("valid ordered terrain profile is required")
    result={**intersections,"events":[dict(v) for v in intersections["events"]]}
    for event in result["events"]:
        if event["stationM"]<stations[0] or event["stationM"]>stations[-1]:raise ValueError("linework event outside terrain profile")
        event["terrainElevationM"]=float(np.interp(event["stationM"],stations,z))
    return result

def audit_mapped_contacts(section,intersections,maximum_vertical_residual_m=2):
    stations=np.asarray(section["stationsM"],float);contacts=section["contactElevationsM"];rows=[]
    for event in intersections["events"]:
        if event["kind"]!="Contact":continue
        index=event.get("contactIndex")
        if isinstance(index,bool) or not isinstance(index,int) or index<0 or index>=len(contacts):raise ValueError("contact event requires a valid contactIndex")
        modeled=float(np.interp(event["stationM"],stations,np.asarray(contacts[index],float)))
        residual=modeled-event["terrainElevationM"]
        rows.append({"featureId":event["featureId"],"contactIndex":index,"stationM":event["stationM"],
          "mappedTerrainElevationM":event["terrainElevationM"],"modeledContactElevationM":modeled,
          "verticalResidualM":residual,"passed":abs(residual)<=maximum_vertical_residual_m,"sourceId":event["sourceId"]})
    return {"contactEventCount":len(rows),"maximumVerticalResidualM":maximum_vertical_residual_m,
      "applicability":"Applicable" if rows else "NotApplicable_NoMappedContacts",
      "passed":bool(rows) and all(v["passed"] for v in rows),"residuals":rows,
      "validationBoundary":"MappedOutcropCompatibility_NotSubsurfaceContinuation"}
