"""Exact piecewise-linear route clipping against an evidence convex hull."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def _cross(ax, ay, bx, by):
    return ax * by - ay * bx


def _clip_segment_to_ccw_convex_polygon(p0, p1, polygon, tolerance):
    """Return the closed parameter interval inside a CCW convex polygon."""
    dx = p1[0] - p0[0]; dy = p1[1] - p0[1]
    lower, upper = 0.0, 1.0
    for index, edge_start in enumerate(polygon):
        edge_end = polygon[(index + 1) % len(polygon)]
        ex = edge_end[0] - edge_start[0]; ey = edge_end[1] - edge_start[1]
        a = _cross(ex, ey, p0[0] - edge_start[0], p0[1] - edge_start[1])
        b = _cross(ex, ey, dx, dy)
        # Interior condition: a + t*b >= -tolerance.
        if abs(b) <= tolerance:
            if a < -tolerance:
                return None
            continue
        crossing = (-tolerance - a) / b
        if b > 0:
            lower = max(lower, crossing)
        else:
            upper = min(upper, crossing)
        if lower > upper + tolerance:
            return None
    return max(0.0, lower), min(1.0, upper)


def intersect_route_with_evidence_hull(surface, route_vertices: Sequence[Mapping]) -> dict:
    """Clip every route segment and evaluate the contact at exact clip endpoints."""
    if (not isinstance(route_vertices, Sequence) or isinstance(route_vertices, (str, bytes))
            or len(route_vertices) < 2):
        raise ValueError("at least two route vertices are required")
    vertices = []
    for item in route_vertices:
        try:
            row = (float(item["stationM"]), float(item["xM"]), float(item["yM"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("route vertex requires stationM, xM and yM") from exc
        if not all(math.isfinite(value) for value in row):
            raise ValueError("route vertices must be finite")
        vertices.append(row)
    if any(right[0] <= left[0] for left, right in zip(vertices, vertices[1:])):
        raise ValueError("route stations must be strictly increasing")
    polygon = [tuple(point) for point in surface.hull]
    if len(polygon) < 3:
        raise ValueError("surface evidence hull is invalid")
    tolerance = surface.hull_tolerance
    pieces = []
    for segment_index, (start, end) in enumerate(zip(vertices, vertices[1:])):
        interval = _clip_segment_to_ccw_convex_polygon(
            start[1:], end[1:], polygon, tolerance)
        if interval is None:
            continue
        t0, t1 = interval
        clipped_length = math.hypot(end[1] - start[1], end[2] - start[2]) * max(t1 - t0, 0.0)
        zero_length_tolerance = max(math.sqrt(max(tolerance, 0.0)),
                                    math.ulp(1.0) * 64)
        if t1 < t0 or clipped_length <= zero_length_tolerance:
            continue
        endpoints = []
        for t in (t0, t1):
            station = start[0] + t * (end[0] - start[0])
            x = start[1] + t * (end[1] - start[1])
            y = start[2] + t * (end[2] - start[2])
            evaluated = surface.evaluate([[x, y]])
            if not bool(evaluated["insideEvidenceHull"][0]):
                raise ValueError("clipped endpoint failed evidence-hull audit")
            endpoints.append({"stationM": station, "xM": x, "yM": y,
                              "contactElevationM": float(evaluated["elevationM"][0])})
        pieces.append({"sourceRouteSegmentIndex": segment_index,
                       "start": endpoints[0], "end": endpoints[1]})
    merged = []
    for piece in pieces:
        if (merged and abs(merged[-1]["end"]["stationM"]
                           - piece["start"]["stationM"]) <= 1e-9):
            merged[-1]["end"] = piece["end"]
            merged[-1]["sourceRouteSegmentIndices"].append(
                piece["sourceRouteSegmentIndex"])
        else:
            merged.append({"start": piece["start"], "end": piece["end"],
                           "sourceRouteSegmentIndices": [piece["sourceRouteSegmentIndex"]]})
    return {"schemaVersion": "ExactRouteEvidenceHullIntersection-1.0",
            "supportedIntervals": merged, "supportedIntervalCount": len(merged),
            "intersectionMethod": "PiecewiseLinearSegmentAgainstCCWConvexHalfPlanes",
            "sampleSpacingDependency": False, "extrapolationAuthorized": False}
