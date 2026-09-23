"""Canonical binding of derived evidence artifacts to one geographic route."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence


def canonical_route(route):
    if not isinstance(route, Sequence) or isinstance(route, (str, bytes)) or len(route) < 2:
        raise ValueError("route requires at least two longitude/latitude vertices")
    result = []
    for point in route:
        if (not isinstance(point, Sequence) or isinstance(point, (str, bytes)) or
                len(point) != 2):
            raise ValueError("route vertices must be longitude/latitude pairs")
        lon, lat = point
        if (isinstance(lon, bool) or isinstance(lat, bool) or
                not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)) or
                not math.isfinite(lon) or not math.isfinite(lat) or
                not -180 <= lon <= 180 or not -85.05112878 <= lat <= 85.05112878):
            raise ValueError("route vertex is outside the supported geographic domain")
        normalized = [float(lon), float(lat)]
        if result and normalized == result[-1]:
            raise ValueError("route contains consecutive duplicate vertices")
        result.append(normalized)
    return result


def route_sha256(route):
    payload = canonical_route(route)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_route_binding(route):
    vertices = canonical_route(route)
    return {"canonicalization": "GEO3D-JCS-LIKE-1.0",
            "routeLonLat": vertices, "routeSha256": route_sha256(vertices)}


def require_matching_route_binding(route, artifact, artifact_name):
    if not isinstance(artifact, dict):
        raise ValueError(f"{artifact_name} must be an object")
    binding = artifact.get("routeBinding")
    if not isinstance(binding, dict):
        raise ValueError(f"{artifact_name} has no route binding")
    expected = build_route_binding(route)
    if binding != expected:
        raise ValueError(f"{artifact_name} route binding mismatch")
    return expected
