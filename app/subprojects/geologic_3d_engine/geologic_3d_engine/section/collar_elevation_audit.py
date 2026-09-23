"""Compare a reported borehole collar with a hash-bound DEM observation."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def audit_collar_against_dem(borehole: Mapping, dem_observation: Mapping,
                             diagnostic_threshold_m: float):
    if not isinstance(borehole, Mapping) or not isinstance(dem_observation, Mapping):
        raise ValueError("borehole and DEM observation must be objects")
    if (isinstance(diagnostic_threshold_m, bool) or
            not isinstance(diagnostic_threshold_m, (int, float)) or
            not math.isfinite(diagnostic_threshold_m) or diagnostic_threshold_m < 0):
        raise ValueError("diagnostic threshold must be a finite non-negative number")
    needed = {"schemaVersion", "sourceId", "sourceUrl", "sourceCrs",
              "verticalReference", "longitude", "latitude", "elevationM",
              "samplingMethod", "rasterArtifactSha256", "recordSha256"}
    if not needed.issubset(dem_observation):
        raise ValueError("DEM observation is incomplete")
    if dem_observation["schemaVersion"] != "PointDemObservation-1.0":
        raise ValueError("unsupported DEM observation")
    unsigned = {k: v for k, v in dem_observation.items() if k != "recordSha256"}
    digest = hashlib.sha256(_canonical(unsigned)).hexdigest()
    if dem_observation["recordSha256"] != digest:
        raise ValueError("DEM observation record hash mismatch")
    tile_hash = dem_observation["rasterArtifactSha256"]
    if (not isinstance(tile_hash, str) or len(tile_hash) != 64 or
            any(c not in "0123456789abcdef" for c in tile_hash)):
        raise ValueError("DEM raster hash is invalid")
    values = [borehole.get("longitude"), borehole.get("latitude"),
              borehole.get("collarElevationM"), dem_observation["longitude"],
              dem_observation["latitude"], dem_observation["elevationM"]]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) for v in values):
        raise ValueError("comparison coordinates and elevations must be finite")
    if borehole.get("horizontalCrs") != dem_observation["sourceCrs"]:
        raise ValueError("borehole and DEM horizontal CRS mismatch")
    if (abs(float(borehole["longitude"]) - float(dem_observation["longitude"])) > 1e-12 or
            abs(float(borehole["latitude"]) - float(dem_observation["latitude"])) > 1e-12):
        raise ValueError("DEM observation is not at the borehole coordinate")
    borehole_vertical = borehole.get("verticalDatum")
    compatible = borehole_vertical == dem_observation["verticalReference"]
    delta = float(dem_observation["elevationM"] - borehole["collarElevationM"])
    absolute = abs(delta)
    if not compatible:
        comparison = "VerticalReferenceUnresolved"
    elif (absolute <= float(diagnostic_threshold_m) or
          math.isclose(absolute, float(diagnostic_threshold_m),
                       rel_tol=1e-12, abs_tol=1e-12)):
        comparison = "ConsistentWithinDiagnosticThreshold"
    else:
        comparison = "DifferenceExceedsDiagnosticThreshold"
    return {
        "schemaVersion": "BoreholeCollarDemComparison-1.0",
        "boreholeSourceId": borehole.get("sourceId"),
        "demSourceId": dem_observation["sourceId"],
        "coordinateLonLat": [float(borehole["longitude"]), float(borehole["latitude"])],
        "reportedCollarElevationM": float(borehole["collarElevationM"]),
        "demElevationM": float(dem_observation["elevationM"]),
        "signedDifferenceM": delta,
        "absoluteDifferenceM": absolute,
        "diagnosticThresholdM": float(diagnostic_threshold_m),
        "verticalReferenceCompatible": compatible,
        "comparisonClass": comparison,
        "collarElevationAccuracyStatus": "Unverified",
        "sectionConstraintAuthorized": False,
        "authorizationBoundary": "DiagnosticComparatorOnly_NotSurveyAccuracyOrVerticalTransformation",
        "demObservation": dict(dem_observation),
    }
