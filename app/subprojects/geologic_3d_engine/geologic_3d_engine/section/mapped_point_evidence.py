"""Normalize and route-project mapped geological point evidence.

Map symbols are retained as evidence of exactly the declared observation.  A
spring, sample locality, or drill-hole symbol without a log never becomes a
lithologic contact or a subsurface section constraint.
"""
from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from .map_template import MeasuredRoute2D


ALLOWED_KINDS = {
    "DrillHoleReachedBasement": "RegionalSubsurfacePresenceOnly_NoIntervals",
    "HotSpring": "SurfaceHydrothermalFeatureOnly",
    "Fumarole": "SurfaceHydrothermalFeatureOnly",
    "ChemicalSampleLocality": "SampleLocalityOnly",
}


def load_gsj_mapped_point_evidence(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "GsjMappedPointEvidence-1.0":
        raise ValueError("unsupported GSJ mapped-point evidence schema")
    claimed = payload.get("recordSha256")
    unsigned = {key:value for key,value in payload.items() if key != "recordSha256"}
    actual = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()
    if claimed != actual:
        raise ValueError("GSJ mapped-point evidence hash mismatch")
    features = payload.get("features")
    if not isinstance(features, list) or payload.get("featureCount") != len(features):
        raise ValueError("GSJ mapped-point feature count mismatch")
    normalized = [normalize_mapped_point(row) for row in features]
    if len({row["featureId"] for row in normalized}) != len(normalized):
        raise ValueError("GSJ mapped-point feature IDs must be unique")
    return {**payload, "features":normalized}


def normalize_mapped_point(record: Mapping):
    required = {"featureId", "longitude", "latitude", "featureKind",
                "sourceLabel", "sourceId", "sourceUrl", "horizontalCrs"}
    if not isinstance(record, Mapping) or not required.issubset(record):
        raise ValueError("mapped point lacks identity, geometry, kind, or provenance")
    lon, lat = record["longitude"], record["latitude"]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) for v in (lon, lat)):
        raise ValueError("mapped-point coordinates must be finite numbers")
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError("mapped-point longitude/latitude are invalid")
    if record["featureKind"] not in ALLOWED_KINDS:
        raise ValueError("unsupported mapped-point feature kind")
    if record["horizontalCrs"] not in {"EPSG:4612", "EPSG:6668", "JGD2000", "JGD2011"}:
        raise ValueError("mapped-point CRS must be explicit JGD2000 or JGD2011")
    for key in required - {"longitude", "latitude"}:
        if not isinstance(record[key], str) or not record[key].strip():
            raise ValueError("mapped-point text fields must be non-empty")
    normalized = {
        **dict(record),
        "longitude": float(lon),
        "latitude": float(lat),
        "interpretationBoundary": ALLOWED_KINDS[record["featureKind"]],
        "sectionConstraintAuthorized": False,
    }
    if record["featureKind"] == "DrillHoleReachedBasement":
        attributes = record.get("sourceAttributes")
        reported = attributes.get("Attribute2") if isinstance(attributes, Mapping) else None
        normalized.update({
            "observationType": "BasementReached",
            "reportedNumericAttribute2": reported,
            "reportedNumericMeaningStatus": "Unverified_GenericSourceAttribute",
            "individualDepthConstraintAuthorized": False,
        })
    return normalized


def project_mapped_points_to_geographic_route(points: Sequence[Mapping], route,
                                               maximum_display_offset_m):
    if (isinstance(maximum_display_offset_m, bool) or
            not isinstance(maximum_display_offset_m, (int, float)) or
            maximum_display_offset_m < 0):
        raise ValueError("maximum_display_offset_m must be non-negative")
    if not isinstance(route, Sequence) or len(route) < 2:
        raise ValueError("route must contain at least two vertices")
    vertices = [[float(p[0]), float(p[1])] for p in route]
    if any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in vertices):
        raise ValueError("route vertices must be finite longitude/latitude pairs")
    lat0 = sum(p[1] for p in vertices) / len(vertices)
    sx = 6378137.0 * math.cos(math.radians(lat0)) * math.pi / 180.0
    sy = 6378137.0 * math.pi / 180.0
    measured = MeasuredRoute2D([[p[0] * sx, p[1] * sy] for p in vertices])
    result = []
    for raw in points:
        item = normalize_mapped_point(raw)
        projection = measured.project([[item["longitude"] * sx, item["latitude"] * sy]])
        offset = float(projection["projectionDistance"][0])
        result.append({
            **item,
            "stationM": float(projection["station"][0]),
            "projectionDistanceM": offset,
            "displayState": "WithinDisplayBuffer" if offset <= maximum_display_offset_m else "OutsideDisplayBuffer",
        })
    return result
