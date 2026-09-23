"""Represent mapped-contact position uncertainty without deriving it from map scale."""
from __future__ import annotations

import math
from collections.abc import Mapping


_METHODS = {"SourceDeclaredGroundZone", "HigherAccuracyComparison",
            "MapScaleOnly", "ProjectDisplayAssumption"}
_EVIDENCE_METHODS = {"SourceDeclaredGroundZone", "HigherAccuracyComparison"}


def _number(value, name, *, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
            not math.isfinite(value) or (positive and value <= 0) or
            (not positive and value < 0)):
        raise ValueError(f"{name} must be a finite {'positive' if positive else 'nonnegative'} number")
    return float(value)


def build_mapped_contact_position_uncertainty(crossing_record: Mapping,
                                               support_record: Mapping,
                                               uncertainty_profile: Mapping):
    """Bind one uncertainty record to every mapped transition and derive certain cores."""
    crossings = crossing_record.get("crossings") if isinstance(crossing_record, Mapping) else None
    intervals = support_record.get("intervals") if isinstance(support_record, Mapping) else None
    records = uncertainty_profile.get("boundaries") if isinstance(uncertainty_profile, Mapping) else None
    if not isinstance(crossings, list) or not isinstance(intervals, list) or not isinstance(records, list):
        raise ValueError("crossings, support intervals, and uncertainty boundaries are required")
    route_length = _number(support_record.get("routeLengthM"), "route length", positive=True)
    transitions = sorted((row for row in crossings
                          if row.get("sideClassificationStatus") == "MappedUnitTransition"),
                         key=lambda row: row.get("stationM", float("nan")))
    if len(intervals) != len(transitions) + 1:
        raise ValueError("support intervals must bracket every mapped transition")
    if len(records) != len(transitions):
        raise ValueError("exactly one uncertainty record is required per mapped transition")
    by_id = {}
    for record in records:
        key = record.get("transitionId") if isinstance(record, Mapping) else None
        if not isinstance(key, str) or not key or key in by_id:
            raise ValueError("uncertainty records require unique transition IDs")
        by_id[key] = record
    boundaries = []
    for index, transition in enumerate(transitions):
        transition_id = f"MAPPED-TRANSITION-{index:04d}"
        if transition_id not in by_id:
            raise ValueError("uncertainty record does not match a mapped transition")
        record = by_id[transition_id]
        method = record.get("method")
        if method not in _METHODS:
            raise ValueError("unknown contact uncertainty method")
        station = _number(transition.get("stationM"), "transition station")
        numeric = method in _EVIDENCE_METHODS or method == "ProjectDisplayAssumption"
        half_width = record.get("halfWidthM")
        if numeric:
            half_width = _number(half_width, "half width")
            lower, upper = max(0.0, station - half_width), min(route_length, station + half_width)
        else:
            if half_width is not None:
                raise ValueError("map scale alone cannot declare a numeric uncertainty width")
            _number(record.get("scaleDenominator"), "scale denominator", positive=True)
            lower = upper = None
        evidence_numeric = method in _EVIDENCE_METHODS
        boundaries.append({
            "transitionId": transition_id,
            "sourceLineFeatureId": transition.get("featureId"),
            "centerStationM": station,
            "method": method,
            "numericHalfWidthM": half_width,
            "lowerStationM": lower,
            "upperStationM": upper,
            "evidenceEligibleNumericZone": evidence_numeric,
            "uncertaintyState": ("EvidenceBoundNumericZone" if evidence_numeric else
                                 "SyntheticDisplayAssumption" if numeric else
                                 "Indeterminate_NumericZoneNotDeclared"),
            "sourceId": record.get("sourceId"),
            "locator": record.get("locator"),
        })
    if set(by_id) != {row["transitionId"] for row in boundaries}:
        raise ValueError("uncertainty profile contains an unknown transition ID")
    cores = []
    for index, interval in enumerate(intervals):
        left = None if index == 0 else boundaries[index - 1]
        right = None if index == len(boundaries) else boundaries[index]
        eligible = ((left is None or left["evidenceEligibleNumericZone"]) and
                    (right is None or right["evidenceEligibleNumericZone"]))
        start = 0.0 if left is None else left["upperStationM"]
        end = route_length if right is None else right["lowerStationM"]
        if not eligible:
            status, start, end = "UnresolvedBoundaryUncertainty", None, None
        elif start > end:
            status, start, end = "NoCertainCore_UncertaintyZonesOverlap", None, None
        else:
            status = "EvidenceBoundCertainCore"
        cores.append({"supportId": interval.get("supportId"), "status": status,
                      "startStationM": start, "endStationM": end,
                      "lengthM": None if start is None else end - start})
    return {
        "schemaVersion": "MappedContactPositionUncertainty-1.0",
        "routeLengthM": route_length,
        "boundaryCount": len(boundaries),
        "boundaries": boundaries,
        "certainCores": cores,
        "evidenceBoundNumericBoundaryCount": sum(
            row["evidenceEligibleNumericZone"] for row in boundaries),
        "numericPositionUncertaintyAuthorized": all(
            row["evidenceEligibleNumericZone"] for row in boundaries),
        "subsurfaceGeometryAuthorized": False,
        "authorizationBoundary": "MappedContactPositionOnly_NoSubsurfaceContinuation",
    }
