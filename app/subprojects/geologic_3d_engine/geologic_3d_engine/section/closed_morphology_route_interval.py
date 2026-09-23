"""Pair route crossings of mapped closed morphology lines."""
from collections import defaultdict


def build_closed_morphology_route_intervals(intersections):
    if intersections.get("interpretationState") != "SurfaceMorphologyEvidence_NoLithologyBoundaryPromotion":
        raise ValueError("typed surface morphology intersections are required")
    grouped=defaultdict(list)
    for event in intersections.get("events",[]):
        if event.get("kind") != "CraterRim":continue
        if event.get("closedMappedLine") is not True:
            raise ValueError("crater route intervals require an explicitly closed mapped line")
        grouped[event.get("featureId")].append(event)
    intervals=[]
    for feature_id,events in sorted(grouped.items()):
        events.sort(key=lambda row:row["stationM"])
        if len(events)%2:
            raise ValueError("a closed morphology line has an unpaired route crossing")
        for index in range(0,len(events),2):
            first,second=events[index:index+2]
            if second["stationM"] <= first["stationM"]:
                raise ValueError("closed morphology crossing order is invalid")
            intervals.append({"intervalId":f"CRATER-ROUTE-INTERVAL-{len(intervals):04d}",
              "featureId":feature_id,"startStationM":first["stationM"],
              "endStationM":second["stationM"],"lengthM":second["stationM"]-first["stationM"],
              "entryTerrainElevationM":first.get("terrainElevationM"),
              "exitTerrainElevationM":second.get("terrainElevationM"),
              "surfaceInterpretation":"InsideMappedCraterPerimeterAlongRoute",
              "lithologyInferenceAuthorized":False,"subsurfaceGeometryAuthorized":False,
              "sourceId":first.get("sourceId")})
    return {"schemaVersion":"ClosedMorphologyRouteIntervals-1.0",
      "routeLengthM":intersections.get("routeLengthM"),
      "intervalCount":len(intervals),"intervals":intervals,
      "authorizationBoundary":"SurfacePerimeterIntervalOnly_NoLithologyOrSubsurfaceInference"}
