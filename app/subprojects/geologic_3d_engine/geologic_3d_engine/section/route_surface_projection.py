"""Project an evidence-bounded contact surface onto ordered route samples."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np


def project_surface_to_route_samples(surface, route_samples: Sequence[Mapping]) -> dict:
    """Evaluate only sampled stations inside the surface's evidence hull.

    Coverage transitions are sample-bracketed, not claimed as exact geometric
    intersections. This preserves the distinction between route sampling
    resolution and geological uncertainty.
    """
    if not isinstance(route_samples, Sequence) or isinstance(route_samples, (str, bytes)):
        raise ValueError("route_samples must be a sequence")
    stations = []
    xy = []
    for item in route_samples:
        if not isinstance(item, Mapping):
            raise ValueError("every route sample must be a mapping")
        try:
            station = float(item["stationM"])
            x = float(item["xM"]); y = float(item["yM"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("route sample requires stationM, xM and yM") from exc
        if not all(math.isfinite(value) for value in (station, x, y)):
            raise ValueError("route sample values must be finite")
        stations.append(station); xy.append([x, y])
    if any(right <= left for left, right in zip(stations, stations[1:])):
        raise ValueError("route sample stations must be strictly increasing")
    result = surface.evaluate(xy)
    inside = np.asarray(result["insideEvidenceHull"], dtype=bool)
    elevation = np.asarray(result["elevationM"], dtype=float)
    if len(inside) != len(stations) or len(elevation) != len(stations):
        raise ValueError("surface result length mismatch")
    samples = [{"stationM": stations[i], "xM": xy[i][0], "yM": xy[i][1],
                "contactElevationM": float(elevation[i]) if inside[i] else None,
                "coverageStatus": "InsideEvidenceHull" if inside[i]
                                  else "UnknownOutsideEvidenceHull"}
               for i in range(len(stations))]
    runs = []
    start = None
    for index, value in enumerate(inside.tolist() + [False]):
        if value and start is None:
            start = index
        elif not value and start is not None:
            end = index - 1
            runs.append({"firstSampleIndex": start, "lastSampleIndex": end,
                         "firstStationM": stations[start], "lastStationM": stations[end]})
            start = None
    brackets = []
    for index in range(1, len(inside)):
        if inside[index] != inside[index - 1]:
            brackets.append({"betweenSampleIndices": [index - 1, index],
                             "stationBracketM": [stations[index - 1], stations[index]],
                             "meaning": "EvidenceHullCrossing_SampleBracketOnly"})
    return {"schemaVersion": "EvidenceBoundedRouteProjection-1.0",
            "sampleCount": len(samples), "supportedSampleCount": int(inside.sum()),
            "samples": samples, "supportedRuns": runs,
            "coverageTransitionBrackets": brackets,
            "transitionPrecision": "RouteSampleBracket_NotExactIntersection",
            "extrapolationAuthorized": False}
