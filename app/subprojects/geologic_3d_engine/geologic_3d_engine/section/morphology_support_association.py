"""Associate mapped morphology intervals with surface supports without naming a volcano."""
from __future__ import annotations

import math


def associate_morphology_with_surface_support(morphology, supports):
    if morphology.get("schemaVersion") != "ClosedMorphologyRouteIntervals-1.0":
        raise ValueError("closed morphology intervals are required")
    if supports.get("schemaVersion") != "MappedSurfaceRouteSupport-1.0":
        raise ValueError("mapped surface supports are required")
    route_a=float(morphology.get("routeLengthM"));route_b=float(supports.get("routeLengthM"))
    if not math.isfinite(route_a) or abs(route_a-route_b)>max(.05,route_b*1e-5):
        raise ValueError("morphology and support routes do not match")
    support_rows=supports.get("intervals");morphology_rows=morphology.get("intervals")
    if not isinstance(support_rows,list) or not isinstance(morphology_rows,list):
        raise ValueError("interval arrays are required")
    results=[]
    for feature in morphology_rows:
        start=float(feature["startStationM"]);end=float(feature["endStationM"])
        overlaps=[]
        for support in support_rows:
            overlap=max(0.0,min(end,float(support["endStationM"]))-
                              max(start,float(support["startStationM"])))
            if overlap:
                overlaps.append({"supportId":support.get("supportId"),"unitId":support.get("unitId"),
                  "symbol":support.get("symbol"),"morphologyClass":support.get("morphologyClass"),
                  "overlapLengthM":overlap,"fractionOfMorphologyInterval":overlap/(end-start)})
        covered=sum(row["overlapLengthM"] for row in overlaps)
        if not math.isclose(covered,end-start,rel_tol=0,abs_tol=1e-6):
            raise ValueError("morphology interval is not fully covered by mapped surface supports")
        classes={row["morphologyClass"] for row in overlaps}
        scoria_only=len(classes)==1 and classes=={"ScoriaConeAndLavaFlowApron"}
        results.append({"intervalId":feature.get("intervalId"),"overlapCount":len(overlaps),
          "overlaps":overlaps,"singleMappedMorphologyClass":next(iter(classes)) if len(classes)==1 else None,
          "scoriaConeMorphometryEligible":scoria_only,
          "namedVolcanoIdentityAuthorized":False,
          "classificationState":("SingleClassSpatialOverlap_NotIdentity" if len(classes)==1 else
                                 "MultipleMappedMorphologyClasses_NoUniqueAssociation")})
    return {"schemaVersion":"MorphologySurfaceSupportAssociation-1.0",
      "associationCount":len(results),"associations":results,
      "scoriaConeMorphometryEligibleCount":sum(row["scoriaConeMorphometryEligible"] for row in results),
      "subsurfaceGeometryAuthorized":False,
      "authorizationBoundary":"SpatialOverlapOnly_NoFeatureIdentityOrSubsurfaceInference"}
