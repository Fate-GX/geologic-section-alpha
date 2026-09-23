"""Compare evidence coverage for an original and proposed evidence route."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _same_route(first, second):
    if not isinstance(first, Sequence) or not isinstance(second, Sequence) or len(first) != len(second):
        return False
    try:
        return all(len(a) == len(b) == 2 and all(abs(float(x)-float(y)) <= 1e-12
            for x, y in zip(a, b)) for a, b in zip(first, second))
    except (TypeError, ValueError):
        return False


def route_turn_angles_degrees(route):
    """Return direction-change angles using a local tangent-plane metric."""
    if not isinstance(route, Sequence) or isinstance(route, (str, bytes)) or len(route) < 2:
        raise ValueError("route requires at least two vertices")
    checked = []
    for point in route:
        if (not isinstance(point, Sequence) or isinstance(point, (str, bytes)) or len(point) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                       not math.isfinite(v) for v in point)):
            raise ValueError("route vertices must be finite longitude/latitude pairs")
        checked.append([float(point[0]), float(point[1])])
    lat0 = math.radians(sum(p[1] for p in checked)/len(checked))
    xy = [[math.radians(p[0])*math.cos(lat0), math.radians(p[1])] for p in checked]
    vectors = [[b[0]-a[0], b[1]-a[1]] for a, b in zip(xy, xy[1:])]
    lengths = [math.hypot(*v) for v in vectors]
    if any(length == 0 for length in lengths):
        raise ValueError("route contains a zero-length segment")
    output = []
    for index, (a, b) in enumerate(zip(vectors, vectors[1:]), start=1):
        cosine = max(-1.0, min(1.0, (a[0]*b[0]+a[1]*b[1])/
                                   (lengths[index-1]*lengths[index])))
        output.append({"vertexIndex": index,
                       "directionChangeDegrees": math.degrees(math.acos(cosine))})
    return output


def _plan_summary(plan):
    if not isinstance(plan, Mapping) or plan.get("schemaVersion") != "PlanEvidenceBundle-1.0":
        raise ValueError("PlanEvidenceBundle-1.0 is required")
    terrain = plan.get("terrainProfile")
    layers = plan.get("layers")
    surface = plan.get("surfaceGeology")
    if (not isinstance(terrain, list) or not terrain or not isinstance(layers, list)
            or not isinstance(surface, Mapping)):
        raise ValueError("plan evidence is incomplete")
    elevations = []
    dem_sources = set()
    for row in terrain:
        value = row.get("elevationM")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("terrain profile contains missing or invalid elevation")
        elevations.append(float(value))
        source = row.get("elevationSourceId") or row.get("demSource")
        if not isinstance(source, str) or not source:
            raise ValueError("terrain sample source is missing")
        dem_sources.add(source)
    layer_sources = {(row.get("evidence_kind"), row.get("source_id")) for row in layers
                     if isinstance(row, Mapping)}
    if len(layer_sources) != len(layers):
        raise ValueError("plan evidence layers are malformed or duplicated")
    counts = {}
    for key in ("mappedUnitIntervals", "transitions", "samples"):
        value = surface.get(key)
        if isinstance(value, list):
            counts[key] = len(value)
        elif isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            counts[key] = value
        else:
            raise ValueError("surface-geology arrays or counts are invalid")
    return {"terrainSampleCount": len(terrain), "terrainComplete": True,
            "terrainElevationRangeM": [min(elevations), max(elevations)],
            "demSourceIds": sorted(dem_sources),
            "layerSources": [list(row) for row in sorted(layer_sources)],
            "surfaceGeologySampleCount": counts["samples"],
            "mappedSurfaceUnitIntervalCount": counts["mappedUnitIntervals"],
            "mappedSurfaceTransitionCount": counts["transitions"]}


def compare_route_plan_evidence(original_plan: Mapping, candidate_plan: Mapping,
                                route_proposal: Mapping,
                                maximum_direction_change_degrees: float = 120.0):
    if not isinstance(route_proposal, Mapping):
        raise ValueError("route proposal must be an object")
    claimed = route_proposal.get("recordSha256")
    unsigned = {k: v for k, v in route_proposal.items() if k != "recordSha256"}
    if claimed != hashlib.sha256(_canonical(unsigned)).hexdigest():
        raise ValueError("route proposal hash mismatch")
    if route_proposal.get("applicationState") != "ProposalOnly_UserMustExplicitlySelect":
        raise ValueError("route proposal application boundary is invalid")
    if not _same_route(original_plan.get("routeLonLat"), route_proposal.get("originalRouteLonLat")):
        raise ValueError("original plan is not bound to the route proposal")
    if not _same_route(candidate_plan.get("routeLonLat"), route_proposal.get("candidateRouteLonLat")):
        raise ValueError("candidate plan is not bound to the route proposal")
    original = _plan_summary(original_plan)
    candidate = _plan_summary(candidate_plan)
    if (isinstance(maximum_direction_change_degrees, bool) or
            not isinstance(maximum_direction_change_degrees, (int, float)) or
            not math.isfinite(maximum_direction_change_degrees) or
            not 0 < maximum_direction_change_degrees < 180):
        raise ValueError("maximum direction change must lie strictly between 0 and 180 degrees")
    original_turns = route_turn_angles_degrees(original_plan["routeLonLat"])
    candidate_turns = route_turn_angles_degrees(candidate_plan["routeLonLat"])
    sharp = [row for row in candidate_turns if
             row["directionChangeDegrees"] > maximum_direction_change_degrees]
    inserted_vertex = route_proposal.get("insertedAfterSegmentIndex")
    if (isinstance(inserted_vertex, bool) or not isinstance(inserted_vertex, int) or
            not 0 <= inserted_vertex < len(candidate_plan["routeLonLat"])-2):
        raise ValueError("route proposal inserted segment index is invalid")
    inserted_vertex += 1
    inserted_turn = next((row for row in candidate_turns
                          if row["vertexIndex"] == inserted_vertex), None)
    inserted_rejected = (inserted_turn is not None and
                         inserted_turn["directionChangeDegrees"] >
                         maximum_direction_change_degrees)
    length = route_proposal.get("candidateLengthM")
    original_length = route_proposal.get("originalLengthM")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0
           for v in (length, original_length)):
        raise ValueError("route proposal lengths are invalid")
    same_sources = original["layerSources"] == candidate["layerSources"]
    return {"schemaVersion": "RoutePlanEvidenceComparison-1.0",
        "routeProposalSha256": claimed,
        "boreholeSourceId": route_proposal.get("sourceId"),
        "original": original, "candidate": candidate,
        "additionalLengthM": float(route_proposal["additionalLengthM"]),
        "lengthRatio": float(length / original_length),
        "terrainSampleIncrease": candidate["terrainSampleCount"]-original["terrainSampleCount"],
        "mappedSurfaceIntervalIncrease": (candidate["mappedSurfaceUnitIntervalCount"]-
                                          original["mappedSurfaceUnitIntervalCount"]),
        "routeGeometryAudit": {
            "maximumAllowedDirectionChangeDegrees": float(maximum_direction_change_degrees),
            "originalTurns": original_turns, "candidateTurns": candidate_turns,
            "candidateSharpTurnCount": len(sharp), "candidateSharpTurns": sharp,
            "insertedVertexTurn": inserted_turn,
            "candidateRouteQuality": "RejectedInsertedSharpBacktracking" if inserted_rejected else "Pass"},
        "declaredEvidenceSourceKindsPreserved": same_sources,
        "comparisonInterpretation": "RouteChangeAlsoChangesObservedSurfaceDomain",
        "sectionConstraintEligibleIfSelected": bool(
            route_proposal.get("sectionConstraintEligibleIfSelected", False)),
        "selectionState": "RejectedForRouteGeometry" if inserted_rejected else "ComparisonOnly_UserDecisionRequired",
        "authorizationBoundary": "PlanEvidenceCoverageComparison_NoAutomaticRouteOrBoreholeAdoption"}
