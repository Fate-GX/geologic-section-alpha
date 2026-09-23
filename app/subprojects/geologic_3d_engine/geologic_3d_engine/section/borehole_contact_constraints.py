"""Convert an observed borehole sequence into point-local contact constraints."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def build_borehole_contact_constraints(
    borehole: Mapping,
    *,
    station_m: float,
    projection_distance_m: float,
    collar_elevation_evidence: Mapping | None = None,
) -> dict:
    """Build interfaces at observed interval bottoms without lateral support.

    Relative depths are direct observations from the log. Absolute elevations
    use ``z_contact = z_collar - depth`` in a positive-up coordinate system,
    but are authorized only when the supplied collar evidence independently
    authorizes an accuracy envelope.
    """
    station = _finite(station_m, "station_m")
    projection = _finite(projection_distance_m, "projection_distance_m")
    if station < 0 or projection < 0:
        raise ValueError("station and projection distance must be non-negative")
    intervals = borehole.get("intervals")
    if not isinstance(intervals, Sequence) or isinstance(intervals, (str, bytes)) or len(intervals) < 2:
        raise ValueError("at least two observed intervals are required")
    contacts = []
    previous_bottom = None
    for index, interval in enumerate(intervals):
        if not isinstance(interval, Mapping) or interval.get("evidenceStatus") != "Observed":
            raise ValueError("every interval must be observed")
        top = _finite(interval.get("topDepthM"), "topDepthM")
        bottom = _finite(interval.get("bottomDepthM"), "bottomDepthM")
        if top < 0 or bottom <= top or (previous_bottom is not None and top != previous_bottom):
            raise ValueError("intervals must be positive and exactly contiguous")
        previous_bottom = bottom
        if index < len(intervals) - 1:
            contacts.append({
                "aboveIntervalIndex": index,
                "belowIntervalIndex": index + 1,
                "depthM": bottom,
                "relativeDepthConstraintAuthorized": True,
                "horizontalSupport": "PointLocalOnly_NoInferredRadius",
                "lateralContinuationAuthorized": False,
            })

    absolute_authorized = False
    if collar_elevation_evidence is not None:
        bounds = collar_elevation_evidence.get("accuracyEnvelopeM")
        absolute_authorized = (
            collar_elevation_evidence.get("sectionConstraintAuthorized") is True
            and isinstance(bounds, Sequence) and not isinstance(bounds, (str, bytes))
            and len(bounds) == 2
        )
        if absolute_authorized:
            lower, upper = map(float, bounds)
            if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
                raise ValueError("invalid collar accuracy envelope")
            for contact in contacts:
                contact["elevationAccuracyEnvelopeM"] = [
                    lower - contact["depthM"], upper - contact["depthM"]]
                contact["absoluteElevationConstraintAuthorized"] = True
    if not absolute_authorized:
        for contact in contacts:
            contact["elevationAccuracyEnvelopeM"] = None
            contact["absoluteElevationConstraintAuthorized"] = False

    return {
        "schemaVersion": "BoreholePointContactConstraints-1.0",
        "boreholeId": borehole.get("boreholeId"),
        "sourceId": borehole.get("sourceId"),
        "stationM": station,
        "projectionDistanceM": projection,
        "contactCount": len(contacts),
        "contacts": contacts,
        "absoluteElevationConstraintAuthorized": absolute_authorized,
        "subsurfaceSurfaceGenerationAuthorized": False,
    }
