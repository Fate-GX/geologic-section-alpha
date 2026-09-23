"""Audit source-declared crater diameters against mapped rim geometry."""
from __future__ import annotations
import math


def _maximum_chord(vertices):
    if not isinstance(vertices,list) or len(vertices)<2:raise ValueError("rim vertices are required")
    lat=sum(float(p[1]) for p in vertices)/len(vertices)
    sx=6378137*math.cos(math.radians(lat))*math.pi/180;sy=6378137*math.pi/180
    points=[]
    for p in vertices:
        if not isinstance(p,list) or len(p)!=2 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in p):
            raise ValueError("rim vertex is invalid")
        points.append((p[0]*sx,p[1]*sy))
    return max(math.hypot(a[0]-b[0],a[1]-b[1]) for a in points for b in points)


def audit_declared_crater_dimensions(linework,profile):
    if linework.get("evidenceRole")!="VolcanicSurfaceMorphology":raise ValueError("volcanic morphology linework is required")
    features={row.get("featureId"):row for row in linework.get("features",[])}
    if None in features or len(features)!=len(linework.get("features",[])):raise ValueError("linework IDs must be unique")
    rims=profile.get("rims")
    if not isinstance(rims,list) or not rims:raise ValueError("declared crater rims are required")
    rows=[]
    for record in rims:
        feature=features.get(record.get("featureId"));declared=record.get("declaredDiameterM")
        if not feature or feature.get("kind")!="CraterRim":raise ValueError("declared rim must reference a crater-rim feature")
        if isinstance(declared,bool) or not isinstance(declared,(int,float)) or not math.isfinite(declared) or declared<=0:
            raise ValueError("declared diameter must be positive")
        measured=_maximum_chord(feature["verticesLonLat"]);ratio=measured/float(declared)
        role=record.get("rimRole")
        if role not in {"OuterClosedRim","InnerRemnantRim"}:raise ValueError("unknown crater rim role")
        if role=="OuterClosedRim" and feature.get("closedMappedLine") is not True:
            raise ValueError("outer closed rim must be closed in the mapped source")
        rows.append({"featureId":feature["featureId"],"rimRole":role,
          "declaredDiameterM":float(declared),"mappedMaximumChordM":measured,
          "mappedToDeclaredRatio":ratio,"dimensionConsistency":
          "ConsistentCandidate_NotSurveyMeasurement" if .75<=ratio<=1.25 else "Inconsistent",
          "diameterUse":"SurfaceMorphologyConstraintOnly","subsurfaceDepthAuthorized":False})
    return {"schemaVersion":"CraterDimensionAudit-1.0","featureName":profile.get("featureName"),
      "rimCount":len(rows),"rims":rows,"allDimensionallyConsistent":all(x["dimensionConsistency"].startswith("Consistent") for x in rows),
      "formationRelations":profile.get("formationRelations",[]),"subsurfaceGeometryAuthorized":False,
      "authorizationBoundary":"MappedSurfaceMorphometryAndNarrativeOnly_NoCraterDepth"}
