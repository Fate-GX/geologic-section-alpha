"""Auditable primitives used by geological forward models.

These reproduce published/local-rate equations, not the complete simulators.
Emergent geometry still requires the original numerical integration, boundary
conditions and calibration.
"""

from __future__ import annotations

import math


def _nonnegative(name: str, value: float) -> float:
    value = float(value)
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _positive(name: str, value: float) -> float:
    value = float(value)
    if value <= 0.0:
        raise ValueError(f"{name} must be positive")
    return value


def badlands_detachment_erosion_rate(
    erodibility: float, precipitation: float, drainage_area: float, slope: float,
    precipitation_exponent: float = 0.0, area_exponent: float = 0.5,
    slope_exponent: float = 1.0,
) -> dict:
    """Badlands detachment-limited stream-power law.

    epsilon_dot = kd * P^l * (P*A)^m * S^n
    Output units depend on the dimensional calibration of kd and input units.
    """
    kd = _nonnegative("erodibility", erodibility)
    p = _nonnegative("precipitation", precipitation)
    area = _nonnegative("drainage_area", drainage_area)
    slope = _nonnegative("slope", slope)
    value = kd * p ** float(precipitation_exponent) * (p * area) ** float(area_exponent) * slope ** float(slope_exponent)
    return {"value": value, "ruleId": "FME-BADLANDS-DETACHMENT-STREAM-POWER",
            "sourceIds": ["BADLANDS-OFFICIAL-PROCESSES"],
            "unitStatus": "DeterminedByCalibratedDimensionalCoefficient",
            "scope": "Process:DetachmentLimitedFluvialIncision"}


def badlands_transport_capacity(
    transportability: float, precipitation: float, drainage_area: float,
    slope: float, area_exponent: float, slope_exponent: float,
) -> dict:
    """Badlands transport-capacity power law Qt=kt*(P*A)^mt*S^nt."""
    kt = _nonnegative("transportability", transportability)
    p = _nonnegative("precipitation", precipitation)
    area = _nonnegative("drainage_area", drainage_area)
    slope = _nonnegative("slope", slope)
    value = kt * (p * area) ** float(area_exponent) * slope ** float(slope_exponent)
    return {"value": value, "ruleId": "FME-BADLANDS-TRANSPORT-CAPACITY",
            "sourceIds": ["BADLANDS-OFFICIAL-PROCESSES"],
            "unitStatus": "DeterminedByCalibratedDimensionalCoefficient",
            "scope": "Process:TransportLimitedFluvial"}


def carbokitten_water_depth(
    relative_sea_level_m: float, topography_m: float,
    integrated_subsidence_m: float = 0.0,
) -> dict:
    """CarboKitten Eq. 1: w=R-eta+integral(sigma dt)."""
    value = float(relative_sea_level_m) - float(topography_m) + float(integrated_subsidence_m)
    return {"value": value, "unit": "m", "ruleId": "FME-CARBOKITTEN-WATER-DEPTH",
            "sourceIds": ["CARBOKITTEN-GMD-2026"]}


def carbokitten_carbonate_production_rate(
    water_depth_m: float, maximum_growth_m_per_myr: float,
    surface_light: float, saturation_light: float, attenuation_per_m: float,
) -> dict:
    """CarboKitten Eq. 3, Bosscher–Schlager-style light-limited production."""
    w = float(water_depth_m)
    gm = _nonnegative("maximum_growth_m_per_myr", maximum_growth_m_per_myr)
    i0 = _nonnegative("surface_light", surface_light)
    ik = float(saturation_light)
    k = _nonnegative("attenuation_per_m", attenuation_per_m)
    if ik <= 0.0:
        raise ValueError("saturation_light must be positive")
    value = 0.0 if w < 0.0 else gm * math.tanh((i0 / ik) * math.exp(-k * w))
    return {"value": value, "unit": "m/Myr", "ruleId": "FME-CARBOKITTEN-CARBONATE-PRODUCTION",
            "sourceIds": ["CARBOKITTEN-GMD-2026"], "scope": "Process:CarbonateProduction"}


def classify_badlands_flux_state(sediment_flux: float, transport_capacity: float) -> dict:
    """Documented conceptual regime based on Qs/Qt; Qt=0 is explicit."""
    qs = _nonnegative("sediment_flux", sediment_flux)
    qt = _nonnegative("transport_capacity", transport_capacity)
    if qt == 0.0:
        state = "NoCapacity_DepositionalIfSedimentPresent" if qs > 0 else "NoFluxNoCapacity"
        ratio = None
    else:
        ratio = qs / qt
        state = "DetachmentDominated" if ratio < 1.0 else ("CapacityBalanced" if ratio == 1.0 else "Depositional")
    return {"sedimentFluxCapacityRatio": ratio, "state": state,
            "ruleId": "FME-BADLANDS-FLUX-REGIME", "sourceIds": ["BADLANDS-OFFICIAL-PROCESSES"]}


def badlands_sediment_flux_incision_factor(ratio: float, law: str) -> dict:
    """Documented Badlands tool/cover factors as a function of Qs/Qt."""
    r = _nonnegative("ratio", ratio)
    if law == "linear_decline":
        value = 1.0 - r
    elif law == "almost_parabolic":
        value = 1.0 - 4.0 * (r - 0.5) ** 2 if r > 0.1 else 2.6 * r + 0.1
    elif law == "dynamic_cover":
        ch = 0.22 if r <= 0.35 else 0.6
        value = math.exp(-((r - 0.35) / ch) ** 2)
    else:
        raise ValueError("unknown sediment-flux incision law")
    return {"value": value, "ratio": r, "law": law,
            "ruleId": "FME-BADLANDS-SEDIMENT-FLUX-FACTOR",
            "sourceIds": ["BADLANDS-OFFICIAL-PROCESSES"],
            "validityNote": "For ratio above capacity, deposition is handled separately."}


def badlands_linear_hillslope_rate(diffusivity_m2_per_time: float,
                                    laplacian_elevation_per_m: float) -> dict:
    """Local form of dz/dt=kappa*Laplacian(z); spatial derivatives come from the solver."""
    kappa = _nonnegative("diffusivity_m2_per_time", diffusivity_m2_per_time)
    return {"value": kappa * float(laplacian_elevation_per_m),
            "ruleId": "FME-BADLANDS-LINEAR-HILLSLOPE-DIFFUSION",
            "sourceIds": ["BADLANDS-OFFICIAL-PROCESSES"],
            "unit": "m/time_unit"}


def badlands_nonlinear_hillslope_flux_factor(slope_magnitude: float,
                                             critical_slope: float) -> dict:
    """Dimensionless multiplier 1/[1-(|grad z|/Sc)^2] used inside divergence."""
    slope = _nonnegative("slope_magnitude", slope_magnitude)
    critical = float(critical_slope)
    if critical <= 0.0 or slope >= critical:
        raise ValueError("requires 0 <= slope < critical_slope; singularity is solver-managed")
    return {"value": 1.0 / (1.0 - (slope / critical) ** 2),
            "ruleId": "FME-BADLANDS-NONLINEAR-HILLSLOPE-FACTOR",
            "sourceIds": ["BADLANDS-OFFICIAL-PROCESSES"]}


def linear_wave_celerity(wavelength_m: float, water_depth_m: float,
                         gravity_m_s2: float = 9.80665) -> dict:
    """Badlands linear-wave-theory celerity c=sqrt(g/k*tanh(kd))."""
    wavelength = _positive("wavelength_m", wavelength_m)
    depth = _nonnegative("water_depth_m", water_depth_m)
    gravity = _positive("gravity_m_s2", gravity_m_s2)
    wave_number = 2.0 * math.pi / wavelength
    value = math.sqrt(gravity / wave_number * math.tanh(wave_number * depth))
    return {"value": value, "unit": "m/s", "waveNumberPerM": wave_number,
            "ruleId": "FME-BADLANDS-LINEAR-WAVE-CELERITY",
            "sourceIds": ["BADLANDS-OFFICIAL-PROCESSES"]}


def carbokitten_active_layer_step(concentration_m: float, delta_time: float,
                                  lithification_half_life: float,
                                  disintegration_rate_m_per_time: float) -> dict:
    """CarboKitten Eq. 8 without production/transport."""
    c = _nonnegative("concentration_m", concentration_m)
    dt = _nonnegative("delta_time", delta_time)
    half_life = _positive("lithification_half_life", lithification_half_life)
    rate = _nonnegative("disintegration_rate_m_per_time", disintegration_rate_m_per_time)
    value = c * 2.0 ** (-dt / half_life) + rate * dt
    return {"value": value, "unit": "m", "ruleId": "FME-CARBOKITTEN-ACTIVE-LAYER-STEP",
            "sourceIds": ["CARBOKITTEN-GMD-2026"]}


def carbokitten_equilibrium_active_layer(disintegration_rate_m_per_time: float,
                                         lithification_half_life: float) -> dict:
    """CarboKitten Eq. 9 limiting equilibrium <C>=rd*tl/ln(2)."""
    rate = _nonnegative("disintegration_rate_m_per_time", disintegration_rate_m_per_time)
    half_life = _positive("lithification_half_life", lithification_half_life)
    return {"value": rate * half_life / math.log(2.0), "unit": "m",
            "ruleId": "FME-CARBOKITTEN-ACTIVE-LAYER-EQUILIBRIUM",
            "sourceIds": ["CARBOKITTEN-GMD-2026"]}
