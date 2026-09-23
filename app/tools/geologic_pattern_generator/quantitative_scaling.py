"""Source-scoped quantitative relations for synthetic geologic sections.

These functions deliberately do not hide calibration, units, or applicability.
They produce candidate dimensions; evidence and topology gates remain mandatory.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pow


class UnverifiedRelationError(ValueError):
    """Raised when a published relation cannot be executed with verified units."""


@dataclass(frozen=True)
class QuantitativeResult:
    value: float
    unit: str
    rule_id: str
    source_ids: tuple[str, ...]
    scope: str
    method: str


def _positive(name: str, value: float) -> float:
    value = float(value)
    if value <= 0.0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def tephra_thickness_half_distance(
    source_thickness_m: float,
    distance_m: float,
    half_distance_m: float,
    background_thickness_m: float = 0.0,
) -> QuantitativeResult:
    """Single exponential segment following Pyle's thickness half-distance.

    This is not an eruption simulator. Multi-segment deposits, erosion and wind-
    directional isopachs require separate evidence and segmentation.
    """
    source = _positive("source_thickness_m", source_thickness_m)
    half_distance = _positive("half_distance_m", half_distance_m)
    distance = float(distance_m)
    background = float(background_thickness_m)
    if distance < 0.0 or background < 0.0 or background >= source:
        raise ValueError("distance/background values are invalid")
    value = background + (source - background) * pow(2.0, -distance / half_distance)
    return QuantitativeResult(value, "m", "QPR-TEPHRA-EXP-HALF-DISTANCE",
                              ("PYLE-TEPHRA-1989",), "Domain:TephraFall",
                              "single_segment_exponential_half_distance")


def relative_lava_length_from_volume(
    reference_length_m: float, erupted_volume_m3: float, reference_volume_m3: float
) -> QuantitativeResult:
    """Calibrated volume-limited basaltic-flow length; exponent 0.67."""
    length = _positive("reference_length_m", reference_length_m)
    volume = _positive("erupted_volume_m3", erupted_volume_m3)
    reference = _positive("reference_volume_m3", reference_volume_m3)
    value = length * pow(volume / reference, 0.67)
    return QuantitativeResult(value, "m", "QPR-LAVA-LENGTH-VOLUME-RELATIVE",
                              ("MARUISHI-LAVA-SCALING-2025",),
                              "Domain:BasalticLava;Regime:VolumeLimited",
                              "reference_calibrated_power_law_exponent_0.67")


def relative_lava_length_from_effusion_rate(
    reference_length_m: float, effusion_rate_m3_s: float, reference_rate_m3_s: float
) -> QuantitativeResult:
    """Calibrated cooling-limited basaltic-flow length; exponent 0.60."""
    length = _positive("reference_length_m", reference_length_m)
    rate = _positive("effusion_rate_m3_s", effusion_rate_m3_s)
    reference = _positive("reference_rate_m3_s", reference_rate_m3_s)
    value = length * pow(rate / reference, 0.60)
    return QuantitativeResult(value, "m", "QPR-LAVA-LENGTH-EFFUSION-RELATIVE",
                              ("MARUISHI-LAVA-SCALING-2025",),
                              "Domain:BasalticLava;Regime:CoolingLimited",
                              "reference_calibrated_power_law_exponent_0.60")


def calibrated_power_law(
    x: float, coefficient: float, exponent: float, *, input_unit: str,
    output_unit: str, source_id: str, rule_id: str, scope: str
) -> QuantitativeResult:
    """Execute a source-specific power law only when provenance and units exist."""
    if not all((input_unit, output_unit, source_id, rule_id, scope)):
        raise ValueError("units, source_id, rule_id and scope are mandatory")
    value = float(coefficient) * pow(_positive("x", x), float(exponent))
    return QuantitativeResult(value, output_unit, rule_id, (source_id,), scope,
                              f"{coefficient}*x^{exponent};input={input_unit}")


def meander_radius_width_diagnostic(radius_m: float, bankfull_width_m: float) -> dict:
    """Soft diagnostic, not an acceptance gate: observed values also occur below 2."""
    ratio = _positive("radius_m", radius_m) / _positive("bankfull_width_m", bankfull_width_m)
    return {
        "ruleId": "QPR-CHANNEL-MEANDER-RADIUS-WIDTH",
        "sourceIds": ["WILLIAMS-MEANDER-1986"],
        "ratio": ratio,
        "reportedModalRange": [2.0, 3.0],
        "status": "WithinReportedModalRange" if 2.0 <= ratio <= 3.0 else "OutsideModalRange_NotRejected",
        "hardGate": False,
    }


def unverified_alluvial_fan_volume_area_relation(*_args, **_kwargs):
    raise UnverifiedRelationError(
        "The reported coefficient/exponent pair is not executable until its area and volume units are verified."
    )
