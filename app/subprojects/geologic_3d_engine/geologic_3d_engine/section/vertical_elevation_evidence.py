"""Preserve reported elevation precision without treating it as survey accuracy."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def build_reported_elevation_envelope(observations: Sequence[Mapping], *, vertical_datum: str):
    """Intersect rounding intervals from compatible published elevations.

    An observation with value ``v`` and display resolution ``r`` represents the
    rounding interval ``[v-r/2, v+r/2]``.  The overlap is a transcription and
    numerical-consistency result only; it is deliberately never an accuracy or
    section-authorization claim.
    """
    if not isinstance(vertical_datum, str) or not vertical_datum.strip():
        raise ValueError("vertical_datum is required")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)) or len(observations) < 2:
        raise ValueError("at least two elevation observations are required")
    rows = []
    for item in observations:
        required = {"sourceId", "sourceUrl", "valueM", "reportingResolutionM",
                    "sourceArtifactSha256"}
        if not isinstance(item, Mapping) or not required.issubset(item):
            raise ValueError("elevation observation lacks value or provenance")
        value = _number(item["valueM"], "valueM")
        resolution = _number(item["reportingResolutionM"], "reportingResolutionM")
        if resolution <= 0:
            raise ValueError("reportingResolutionM must be positive")
        digest = item["sourceArtifactSha256"]
        if (not isinstance(digest, str) or len(digest) != 64 or
                any(c not in "0123456789abcdef" for c in digest)):
            raise ValueError("sourceArtifactSha256 must be lowercase SHA-256")
        if not all(isinstance(item[key], str) and item[key].strip()
                   for key in ("sourceId", "sourceUrl")):
            raise ValueError("source identity and URL are required")
        rows.append({**dict(item), "roundingLowerM": value-resolution/2,
                     "roundingUpperM": value+resolution/2})
    lower = max(row["roundingLowerM"] for row in rows)
    upper = min(row["roundingUpperM"] for row in rows)
    consistent = lower <= upper
    record = {
        "schemaVersion": "ReportedElevationEnvelope-1.0",
        "verticalDatum": vertical_datum.strip(),
        "observations": rows,
        "roundingIntersectionM": [lower, upper] if consistent else None,
        "roundingUnionM": [min(row["roundingLowerM"] for row in rows),
                           max(row["roundingUpperM"] for row in rows)],
        "consistencyStatus": ("NumericallyConsistent_NotAccuracyEvidence" if consistent
                              else "ConflictingPublishedElevations"),
        "collarElevationAccuracyStatus": "Unverified",
        "sectionConstraintAuthorized": False,
        "interpretationBoundary": (
            "Reporting resolution is not measurement accuracy; the interval must not "
            "authorize subsurface geometry."),
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    record["recordSha256"] = hashlib.sha256(canonical).hexdigest()
    return record


def translate_depth_to_elevation_envelope(envelope: Mapping, depths_m: Sequence[float]):
    """Translate a compatible collar rounding interval to depth-bound elevations."""
    if (not isinstance(envelope, Mapping) or
            envelope.get("schemaVersion") != "ReportedElevationEnvelope-1.0" or
            envelope.get("consistencyStatus") != "NumericallyConsistent_NotAccuracyEvidence"):
        raise ValueError("a consistent reported-elevation envelope is required")
    bounds = envelope.get("roundingIntersectionM")
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise ValueError("rounding intersection is missing")
    output = []
    for depth in depths_m:
        depth = _number(depth, "depthM")
        if depth < 0:
            raise ValueError("depthM must be non-negative")
        output.append({"depthM": depth,
                       "elevationEnvelopeM": [float(bounds[0]-depth),
                                               float(bounds[1]-depth)],
                       "meaning": "ReportingPrecisionEnvelope_NotAccuracyInterval",
                       "sectionConstraintAuthorized": False})
    return output
