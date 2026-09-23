"""DC resistivity calculations and fail-closed geological evidence classification."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Mapping


def schlumberger_apparent_resistivity(*, potential_difference_v: float,
                                      current_a: float,
                                      current_electrode_spacing_m: float,
                                      potential_electrode_spacing_m: float) -> dict:
    """Calculate apparent resistivity for a symmetric Schlumberger array.

    The result is a bulk response of the sampled half-space.  It is not a true
    layer resistivity except for a homogeneous, isotropic subsurface.
    """
    values = (potential_difference_v, current_a, current_electrode_spacing_m,
              potential_electrode_spacing_m)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) for v in values):
        raise ValueError("Schlumberger inputs must be finite numbers")
    if potential_difference_v <= 0 or current_a <= 0:
        raise ValueError("potential difference and current must be positive")
    if current_electrode_spacing_m <= 0 or potential_electrode_spacing_m <= 0:
        raise ValueError("electrode spacings must be positive")
    if current_electrode_spacing_m < 5.0 * potential_electrode_spacing_m:
        raise ValueError("Schlumberger geometry requires AB to be at least five times MN")
    half_ab = current_electrode_spacing_m / 2.0
    half_mn = potential_electrode_spacing_m / 2.0
    factor = math.pi * (half_ab * half_ab - half_mn * half_mn) / potential_electrode_spacing_m
    apparent = factor * potential_difference_v / current_a
    return {
        "geometricFactorM": factor,
        "apparentResistivityOhmM": apparent,
        "equationId": "SCHLUMBERGER-APPARENT-RESISTIVITY-1",
        "interpretationBoundary": "BulkApparentProperty_NotDirectLithologyOrTrueLayerResistivity",
    }


def assess_resistivity_interpretation(record: Mapping) -> dict:
    """Classify whether an interpreted resistivity model may constrain a section."""
    required = {
        "sourceId", "method", "rawMeasurementsAvailable",
        "soundingCoordinatesAvailable", "inversionDetailsAvailable",
        "horizontalReferenceStatus", "verticalReferenceStatus",
        "interpretedLayers", "lithologyCalibrationStatus",
        "independentReviewStatus",
    }
    if not isinstance(record, Mapping) or not required.issubset(record):
        raise ValueError("resistivity interpretation record is incomplete")
    if record["method"] not in {"SchlumbergerVES", "Wenner", "WennerSchlumberger", "ERT"}:
        raise ValueError("unsupported resistivity acquisition method")
    for key in ("rawMeasurementsAvailable", "soundingCoordinatesAvailable",
                "inversionDetailsAvailable"):
        if not isinstance(record[key], bool):
            raise ValueError(f"{key} must be boolean")
    allowed_reference = {"Verified", "Declared", "Unverified"}
    if record["horizontalReferenceStatus"] not in allowed_reference or \
       record["verticalReferenceStatus"] not in allowed_reference:
        raise ValueError("invalid coordinate-reference status")
    layers = record["interpretedLayers"]
    if not isinstance(layers, list):
        raise ValueError("interpreted resistivity layers must be a list")
    previous_bottom = 0.0
    for layer in layers:
        if not isinstance(layer, Mapping) or not {"topDepthM", "bottomDepthM",
                                                  "resistivityOhmM"}.issubset(layer):
            raise ValueError("interpreted resistivity layer is incomplete")
        top, bottom, rho = layer["topDepthM"], layer["bottomDepthM"], layer["resistivityOhmM"]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
               not math.isfinite(v) for v in (top, bottom, rho)):
            raise ValueError("interpreted layer values must be finite numbers")
        if top != previous_bottom or bottom <= top or rho <= 0:
            raise ValueError("resistivity layers must be contiguous, ordered and positive")
        previous_bottom = float(bottom)
    physical = (
        record["rawMeasurementsAvailable"] and
        record["soundingCoordinatesAvailable"] and
        record["inversionDetailsAvailable"] and
        bool(layers) and
        record["horizontalReferenceStatus"] in {"Verified", "Declared"} and
        record["verticalReferenceStatus"] in {"Verified", "Declared"}
    )
    lithology = (
        physical and
        record["lithologyCalibrationStatus"] == "CollocatedObservedLithology" and
        record["independentReviewStatus"] == "IndependentlyVerified"
    )
    reasons = []
    if not record["rawMeasurementsAvailable"]:
        reasons.append("RawMeasurementsUnavailable")
    if not record["soundingCoordinatesAvailable"]:
        reasons.append("SoundingCoordinatesUnavailable")
    if not record["inversionDetailsAvailable"]:
        reasons.append("InversionDetailsUnavailable")
    if not layers:
        reasons.append("InterpretedLayerGeometryUnavailable")
    if record["horizontalReferenceStatus"] not in {"Verified", "Declared"}:
        reasons.append("HorizontalReferenceUnverified")
    if record["verticalReferenceStatus"] not in {"Verified", "Declared"}:
        reasons.append("VerticalReferenceUnverified")
    if record["lithologyCalibrationStatus"] != "CollocatedObservedLithology":
        reasons.append("NoCollocatedLithologyCalibration")
    if record["independentReviewStatus"] != "IndependentlyVerified":
        reasons.append("IndependentReviewMissing")
    payload = {
        "sourceId": record["sourceId"],
        "physicalPropertyConstraintAuthorized": physical,
        "lithologyBoundaryAuthorized": lithology,
        "blockingReasons": reasons,
        "interpretationBoundary": (
            "ResistivityBoundaryMayConstrainPhysicalPropertyOnly"
            if physical and not lithology else
            "ReviewedCollocatedCalibrationRequiredForLithology"
        ),
    }
    payload["recordSha256"] = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    return payload
