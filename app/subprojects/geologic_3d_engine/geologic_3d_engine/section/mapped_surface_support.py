"""Build exact-on-map surface support intervals along an arbitrary route."""
from __future__ import annotations

import math
from collections.abc import Mapping


def build_mapped_surface_support_intervals(crossing_record: Mapping,
                                           route_length_m,
                                           morphology_assignment: Mapping):
    if (isinstance(route_length_m, bool) or
            not isinstance(route_length_m, (int, float)) or
            not math.isfinite(route_length_m) or route_length_m <= 0):
        raise ValueError("route length must be a positive finite number")
    crossings = crossing_record.get("crossings") if isinstance(crossing_record, Mapping) else None
    units = morphology_assignment.get("units") if isinstance(morphology_assignment, Mapping) else None
    if not isinstance(crossings, list) or not isinstance(units, list):
        raise ValueError("crossings and morphology assignments are required")
    by_feature = {unit.get("sourcePolygonFeatureId"): unit for unit in units}
    if None in by_feature or len(by_feature) != len(units):
        raise ValueError("morphology units require unique source polygon feature IDs")
    transitions = [row for row in crossings
                   if row.get("sideClassificationStatus") == "MappedUnitTransition"]
    transitions.sort(key=lambda row: row.get("stationM", float("nan")))
    previous_station = 0.0
    pairs = []
    for transition in transitions:
        station = transition.get("stationM")
        if (isinstance(station, bool) or not isinstance(station, (int, float)) or
                not math.isfinite(station) or not previous_station < station < route_length_m):
            raise ValueError("mapped transitions must be strictly ordered inside the route")
        pair = transition.get("unitPair")
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("mapped transition requires exactly two adjacent units")
        ids = [item.get("sourcePolygonFeatureId") if isinstance(item, Mapping) else None
               for item in pair]
        if ids[0] not in by_feature or ids[1] not in by_feature or ids[0] == ids[1]:
            raise ValueError("mapped transition references unknown or identical units")
        if pairs and pairs[-1][1] != ids[0]:
            raise ValueError("mapped transition unit chain is discontinuous")
        pairs.append(ids)
        previous_station = float(station)
    if not transitions:
        raise ValueError("at least one mapped-unit transition is required")
    bounds = [0.0] + [float(row["stationM"]) for row in transitions] + [float(route_length_m)]
    feature_ids = [pairs[0][0]] + [pair[1] for pair in pairs]
    intervals = []
    component_counts = {}
    for start, end, feature_id in zip(bounds[:-1], bounds[1:], feature_ids):
        if end <= start:
            raise ValueError("surface support interval must have positive length")
        unit = by_feature[feature_id]
        component_counts[feature_id] = component_counts.get(feature_id, 0) + 1
        intervals.append({
            "supportId": f"SURFACE-SUPPORT-{len(intervals):04d}",
            "unitId": unit["unitId"],
            "sourcePolygonFeatureId": feature_id,
            "symbol": unit.get("symbol"),
            "componentIndexForUnit": component_counts[feature_id] - 1,
            "startStationM": start,
            "endStationM": end,
            "lengthM": end - start,
            "morphologyClass": unit.get("morphologyClass"),
            "finiteBodyRequired": bool(unit.get("finiteBodyRequired")),
            "supportSurface": "TerrainOnly",
            "bottomSurfaceStatus": "Unresolved",
            "lateralGapBridgingAuthorized": False,
            "numericSubsurfaceGeometryAuthorized": False,
        })
    return {
        "schemaVersion": "MappedSurfaceRouteSupport-1.0",
        "routeLengthM": float(route_length_m),
        "mappedTransitionCount": len(transitions),
        "ignoredNonTransitionCrossingCount": len(crossings) - len(transitions),
        "supportIntervalCount": len(intervals),
        "intervals": intervals,
        "unitComponentCounts": {
            by_feature[key]["unitId"]: count for key, count in component_counts.items()
        },
        "subsurfaceGeometryAuthorized": False,
        "authorizationBoundary":
            "MappedTerrainSupportOnly_NoBottomSurfaceAndNoGapBridging",
    }
