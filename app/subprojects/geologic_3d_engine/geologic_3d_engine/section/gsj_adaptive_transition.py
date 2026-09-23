"""Adaptively narrow interval-censored GSJ surface-unit transitions."""
from __future__ import annotations

import math
import copy
from typing import Callable, Mapping

from .gsj_surface_geology import GSJ_API_VERSION, validate_legend
from .gsj_transition_review import canonical_sha256


def _finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _route_position(profile, station):
    if not isinstance(profile, list) or len(profile) < 2:
        raise ValueError("terrain profile requires at least two samples")
    previous = -math.inf
    for row in profile:
        if not isinstance(row, Mapping) or not {"stationM", "longitude", "latitude"}.issubset(row):
            raise ValueError("terrain profile lacks station or coordinates")
        current = _finite_number(row["stationM"], "stationM")
        if current <= previous:
            raise ValueError("terrain profile stations must be strictly increasing")
        previous = current
    if station < float(profile[0]["stationM"]) or station > float(profile[-1]["stationM"]):
        raise ValueError("transition bracket lies outside terrain profile")
    for left, right in zip(profile[:-1], profile[1:]):
        lo, hi = float(left["stationM"]), float(right["stationM"])
        if lo <= station <= hi:
            fraction = (station-lo)/(hi-lo)
            longitude = float(left["longitude"])+fraction*(float(right["longitude"])-float(left["longitude"]))
            latitude = float(left["latitude"])+fraction*(float(right["latitude"])-float(left["latitude"]))
            if not math.isfinite(longitude) or not math.isfinite(latitude):
                raise ValueError("interpolated route coordinates must be finite")
            return longitude, latitude
    raise ValueError("station could not be located on terrain profile")


def refine_surface_transition(plan: Mapping, transition_index: int,
                              query_point: Callable[[float, float], Mapping],
                              target_width_m: float = 10.0,
                              maximum_queries: int = 20):
    """Narrow one two-class GSJ transition without inventing an exact contact.

    Binary refinement is valid only while every added sample belongs to one of
    the two endpoint units. A third unit or an unmapped sample invalidates that
    simple-boundary assumption and ends refinement without a usable bracket.
    """
    if not isinstance(plan, Mapping) or not callable(query_point):
        raise ValueError("plan and query function are required")
    if isinstance(transition_index, bool) or not isinstance(transition_index, int) or transition_index < 0:
        raise ValueError("transition index must be a non-negative integer")
    target = _finite_number(target_width_m, "target_width_m")
    if target <= 0:
        raise ValueError("target width must be positive")
    if isinstance(maximum_queries, bool) or not isinstance(maximum_queries, int) or not 1 <= maximum_queries <= 30:
        raise ValueError("maximum queries must be an integer in [1,30]")

    transitions = plan.get("surfaceGeology", {}).get("transitions", [])
    if transition_index >= len(transitions):
        raise ValueError("transition index is out of range")
    transition = transitions[transition_index]
    left_symbol, right_symbol = transition.get("leftSymbol"), transition.get("rightSymbol")
    if not left_symbol or not right_symbol or left_symbol == right_symbol:
        raise ValueError("adaptive refinement requires two different mapped endpoint units")
    lower = _finite_number(transition.get("lowerStationM"), "lowerStationM")
    upper = _finite_number(transition.get("upperStationM"), "upperStationM")
    if lower >= upper:
        raise ValueError("transition bracket must have positive width")
    profile = plan.get("terrainProfile")
    _route_position(profile, lower)
    _route_position(profile, upper)
    original = {"lowerStationM": lower, "upperStationM": upper,
                "leftSymbol": left_symbol, "rightSymbol": right_symbol}
    trace = []
    status = "ResolvedToRequestedBracket" if upper-lower <= target else None

    while status is None and len(trace) < maximum_queries:
        station = 0.5*(lower+upper)
        longitude, latitude = _route_position(profile, station)
        raw = query_point(latitude, longitude)
        legend = None if isinstance(raw, Mapping) and not raw.get("symbol") else validate_legend(raw)
        symbol = None if legend is None else legend["symbol"]
        trace.append({"queryIndex": len(trace), "stationM": station,
                      "longitude": longitude, "latitude": latitude,
                      "symbol": symbol, "sampleStatus": "Mapped" if legend else "NoMappedUnit",
                      "legend": legend})
        if symbol == left_symbol:
            lower = station
        elif symbol == right_symbol:
            upper = station
        else:
            status = "InterruptedByNoMappedUnit" if symbol is None else "InterruptedByThirdMappedUnit"
            break
        if upper-lower <= target:
            status = "ResolvedToRequestedBracket"
    if status is None:
        status = "MaximumQueriesReached"

    usable = status in {"ResolvedToRequestedBracket", "MaximumQueriesReached"}
    bracket = None if not usable else {
        "lowerStationM": lower, "upperStationM": upper,
        "estimatedStationM": 0.5*(lower+upper),
        "uncertaintyM": 0.5*(upper-lower),
        "locatorStatus": "AdaptivelyRefinedIntervalBetweenPointQueries"}
    return {"schemaVersion": "GsjAdaptiveTransitionRefinement-1.0",
            "planSha256": canonical_sha256(plan),
            "transitionId": f"GSJ-TRANSITION-{transition_index}",
            "sourceId": "GSJ-SEAMLESS-V2-API", "apiVersion": GSJ_API_VERSION,
            "originalBracket": original, "targetWidthM": target,
            "maximumQueries": maximum_queries, "queryTrace": trace,
            "refinementStatus": status, "refinedBracket": bracket,
            "reviewEligibility": "Eligible" if usable else "Ineligible_AmbiguousTransition",
            "interpretationBoundary": "MappedSurfaceTransitionBracket_NotExactMapLineOrSubsurfaceContact"}


def apply_transition_refinement(plan: Mapping, refinement: Mapping):
    """Return a copied plan whose one transition uses an artifact-bound bracket."""
    if not isinstance(plan, Mapping) or not isinstance(refinement, Mapping):
        raise ValueError("plan and refinement are required")
    if refinement.get("schemaVersion") != "GsjAdaptiveTransitionRefinement-1.0":
        raise ValueError("unsupported refinement schema")
    if refinement.get("planSha256") != canonical_sha256(plan):
        raise ValueError("refinement is not bound to this plan evidence")
    if refinement.get("reviewEligibility") != "Eligible" or not isinstance(refinement.get("refinedBracket"), Mapping):
        raise ValueError("ambiguous refinement cannot replace a transition bracket")
    prefix = "GSJ-TRANSITION-"
    transition_id = refinement.get("transitionId")
    if not isinstance(transition_id, str) or not transition_id.startswith(prefix):
        raise ValueError("invalid transition identifier")
    try:
        index = int(transition_id[len(prefix):])
    except ValueError as exc:
        raise ValueError("invalid transition identifier") from exc
    result = copy.deepcopy(plan)
    transitions = result.get("surfaceGeology", {}).get("transitions", [])
    if index < 0 or index >= len(transitions):
        raise ValueError("transition index is out of range")
    expected = refinement.get("originalBracket", {})
    actual = transitions[index]
    for key in ("lowerStationM", "upperStationM", "leftSymbol", "rightSymbol"):
        if expected.get(key) != actual.get(key):
            raise ValueError("refinement original bracket disagrees with plan")
    bracket = refinement["refinedBracket"]
    for key in ("lowerStationM", "upperStationM", "estimatedStationM", "uncertaintyM", "locatorStatus"):
        actual[key] = bracket[key]
    actual["adaptiveRefinement"] = {
        "schemaVersion": refinement["schemaVersion"],
        "sourcePlanSha256": refinement["planSha256"],
        "refinementStatus": refinement["refinementStatus"],
        "queryTrace": copy.deepcopy(refinement["queryTrace"])}
    return result
