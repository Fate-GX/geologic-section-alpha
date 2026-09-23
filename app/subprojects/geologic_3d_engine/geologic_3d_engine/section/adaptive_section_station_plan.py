"""Plan exact section stations before querying terrain at added locations."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def _route_xy_at_station(vertices, station):
    for start, end in zip(vertices, vertices[1:]):
        if start[0] <= station <= end[0]:
            fraction = (station - start[0]) / (end[0] - start[0])
            return (start[1] + fraction * (end[1] - start[1]),
                    start[2] + fraction * (end[2] - start[2]))
    raise ValueError("station lies outside route")


def build_adaptive_section_station_plan(
        route_vertices: Sequence[Mapping], exact_contact_coverages: Sequence[Mapping],
        *, merge_tolerance_m: float) -> dict:
    """Union route vertices and exact evidence-hull endpoints without inventing Z."""
    if (isinstance(merge_tolerance_m, bool)
            or not isinstance(merge_tolerance_m, (int, float))
            or not math.isfinite(merge_tolerance_m) or merge_tolerance_m < 0):
        raise ValueError("merge_tolerance_m must be finite and non-negative")
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
            raise ValueError("route vertex values must be finite")
        vertices.append(row)
    if any(right[0] <= left[0] for left, right in zip(vertices, vertices[1:])):
        raise ValueError("route stations must be strictly increasing")
    candidates = [{"stationM": row[0], "xM": row[1], "yM": row[2],
                   "reasons": ["OriginalRouteVertex"]} for row in vertices]
    for coverage_index, coverage in enumerate(exact_contact_coverages):
        if coverage.get("schemaVersion") != "ExactRouteEvidenceHullIntersection-1.0":
            raise ValueError("invalid exact contact coverage")
        for interval_index, interval in enumerate(coverage.get("supportedIntervals", [])):
            for endpoint_name in ("start", "end"):
                endpoint = interval[endpoint_name]
                station = float(endpoint["stationM"])
                x, y = _route_xy_at_station(vertices, station)
                if (abs(x-float(endpoint["xM"])) > merge_tolerance_m
                        or abs(y-float(endpoint["yM"])) > merge_tolerance_m):
                    raise ValueError("coverage endpoint is not on the declared route")
                candidates.append({"stationM": station, "xM": x, "yM": y,
                                   "reasons": [f"ContactCoverage{coverage_index}:"
                                               f"Interval{interval_index}:{endpoint_name}"]})
    candidates.sort(key=lambda item: item["stationM"])
    merged = []
    for item in candidates:
        if merged and abs(item["stationM"] - merged[-1]["stationM"]) <= merge_tolerance_m:
            if (abs(item["xM"] - merged[-1]["xM"]) > merge_tolerance_m
                    or abs(item["yM"] - merged[-1]["yM"]) > merge_tolerance_m):
                raise ValueError("near-equal stations disagree in XY")
            merged[-1]["reasons"].extend(item["reasons"])
        else:
            merged.append(dict(item))
    for item in merged:
        item["terrainElevationM"] = None
        item["terrainEvidenceRequired"] = True
        item["isInsertedExactBoundary"] = "OriginalRouteVertex" not in item["reasons"]
        item["reasons"] = sorted(set(item["reasons"]))
    return {"schemaVersion": "AdaptiveSectionStationPlan-1.0",
            "stationCount": len(merged),
            "insertedExactBoundaryCount": sum(item["isInsertedExactBoundary"] for item in merged),
            "stations": merged,
            "terrainCompletionStatus": "PendingDirectDemSampling",
            "terrainLinearInterpolationAuthorized": False,
            "mergeToleranceM": float(merge_tolerance_m)}


def attach_direct_terrain_evidence(station_plan: Mapping,
                                   terrain_observations: Sequence[Mapping]) -> dict:
    """Complete a station plan only with one hash-bound direct DEM result per station."""
    if station_plan.get("schemaVersion") != "AdaptiveSectionStationPlan-1.0":
        raise ValueError("AdaptiveSectionStationPlan-1.0 is required")
    stations = station_plan.get("stations", [])
    if len(terrain_observations) != len(stations):
        raise ValueError("one terrain observation per planned station is required")
    completed = []
    for planned, observed in zip(stations, terrain_observations):
        try:
            observed_station = float(observed.get("stationM"))
            elevation = float(observed.get("elevationM"))
        except (TypeError, ValueError) as exc:
            raise ValueError("terrain observation requires numeric station and elevation") from exc
        if observed_station != float(planned["stationM"]):
            raise ValueError("terrain observation station mismatch")
        digest = observed.get("sourceArtifactSha256")
        source_id = observed.get("sourceId")
        if not math.isfinite(elevation):
            raise ValueError("terrain elevation must be finite")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)):
            raise ValueError("terrain observation requires lowercase SHA-256")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("terrain observation requires sourceId")
        completed.append({**dict(planned), "terrainElevationM": elevation,
                          "terrainEvidenceRequired": False,
                          "terrainSourceId": source_id,
                          "terrainSourceArtifactSha256": digest})
    return {**dict(station_plan), "stations": completed,
            "terrainCompletionStatus": "CompleteDirectDemSampling"}


def sample_adaptive_plan_from_xyz_dem(station_plan: Mapping, route_lonlat,
                                      elevation_sampler, *, source_id,
                                      dem_artifact_sha256,
                                      sampling_method="NearestPixel") -> dict:
    """Sample every planned station directly from an immutable XYZ DEM source."""
    from .plan_evidence import sample_geographic_route_at_stations
    if station_plan.get("schemaVersion") != "AdaptiveSectionStationPlan-1.0":
        raise ValueError("AdaptiveSectionStationPlan-1.0 is required")
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("source_id is required")
    if (not isinstance(dem_artifact_sha256, str) or len(dem_artifact_sha256) != 64
            or any(char not in "0123456789abcdef" for char in dem_artifact_sha256)):
        raise ValueError("dem_artifact_sha256 must be lowercase SHA-256")
    targets = [row["stationM"] for row in station_plan["stations"]]
    sampled = sample_geographic_route_at_stations(route_lonlat, targets,
                                                  elevation_sampler,
                                                  sampling_method=sampling_method)
    if any(row["elevationM"] is None for row in sampled):
        raise ValueError("DEM contains NoData at an adaptive section station")
    observations = [{"stationM": row["stationM"], "elevationM": row["elevationM"],
                     "sourceId": source_id,
                     "sourceArtifactSha256": dem_artifact_sha256,
                     "longitude": row["longitude"], "latitude": row["latitude"],
                     "routeSegmentIndex": row["routeSegmentIndex"],
                     "resolvedElevationSourceId": row.get("elevationSourceId")}
                    for row in sampled]
    completed = attach_direct_terrain_evidence(station_plan, observations)
    for destination, observation in zip(completed["stations"], observations):
        destination.update({key: observation[key]
                            for key in ("longitude", "latitude", "routeSegmentIndex",
                                        "resolvedElevationSourceId")})
    completed["terrainSamplingMethod"] = sampling_method
    completed["demArtifactSha256"] = dem_artifact_sha256
    return completed
