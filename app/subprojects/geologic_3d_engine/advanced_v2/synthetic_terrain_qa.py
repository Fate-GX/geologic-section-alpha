"""Deterministic multi-scale terrain fixtures for Advanced V2 QA.

These profiles are deliberately *not* substitutes for DEM evidence.  They are
used only to exercise drafting and morphology gates with terrain that contains
ridge asymmetry, drainage-scale incision and short-wavelength roughness.
"""
from __future__ import annotations

import math
import random


def multiscale_mountain_profile(stations_m, *, seed: int = 880102):
    x = [float(value) for value in stations_m]
    if len(x) < 21 or any(b <= a for a, b in zip(x, x[1:])):
        raise ValueError("at least 21 ordered stations are required")
    span = x[-1] - x[0]
    rng = random.Random(int(seed))
    phases = [rng.uniform(0.0, 2.0 * math.pi) for _ in range(9)]
    values = []
    for station in x:
        u = (station - x[0]) / span
        # Broad asymmetric ridge and shoulder; the smaller terms represent
        # ridge/gully scales rather than display-time smoothing.
        broad = 128.0 * math.exp(-((u - 0.43) / 0.29) ** 2)
        shoulder = 54.0 * math.exp(-((u - 0.79) / 0.16) ** 2)
        incision = -31.0 * math.exp(-((u - 0.61) / 0.055) ** 2)
        # Local landform elements prevent one analytic bell from carrying the
        # whole profile.  They are synthetic QA features, never DEM substitutes.
        local_landforms = (
            15.0 * math.exp(-((u - 0.18) / 0.045) ** 2)
            - 18.0 * math.exp(-((u - 0.29) / 0.035) ** 2)
            + 13.0 * math.exp(-((u - 0.51) / 0.030) ** 2)
            - 16.0 * math.exp(-((u - 0.88) / 0.040) ** 2)
        )
        texture = 0.0
        for octave in range(9):
            frequency = 1.35 * (1.72 ** octave)
            amplitude = 19.0 / (frequency ** 1.06)
            texture += amplitude * math.sin(2.0 * math.pi * frequency * u + phases[octave])
        values.append(405.0 + 24.0 * u + broad + shoulder + incision + local_landforms + texture)
    return values


def audit_natural_terrain_texture(stations_m, elevations_m, *, synthetic_test_only=True):
    x = [float(value) for value in stations_m]
    z = [float(value) for value in elevations_m]
    if len(x) != len(z) or len(x) < (21 if synthetic_test_only else 2):
        raise ValueError("paired terrain samples are required")
    if not all(math.isfinite(value) for value in x+z) or any(b <= a for a,b in zip(x,x[1:])):
        raise ValueError("finite terrain elevations and strictly increasing stations are required")
    slopes = [(b_z-a_z)/(b_x-a_x) for a_x, b_x, a_z, b_z in zip(x, x[1:], z, z[1:])]
    curvature = [right-left for left, right in zip(slopes, slopes[1:])]
    turning = sum(left * right < 0.0 for left, right in zip(slopes, slopes[1:]))
    active_curvature = sum(abs(value) > 0.012 for value in curvature)
    relief = max(z) - min(z)
    span = x[-1] - x[0]
    # Remove an 11-sample moving mean and require visible drainage/ridge-scale
    # residual relief.  This closes the former loophole where tiny oscillations
    # on one smooth mound satisfied turning-count checks.
    radius = 5
    smooth = []
    for index in range(len(z)):
        left, right = max(0, index-radius), min(len(z), index+radius+1)
        smooth.append(sum(z[left:right])/(right-left))
    residual = [value-background for value, background in zip(z, smooth)]
    local_relief = max(residual)-min(residual)
    local_relief_fraction = local_relief/relief if relief > 0 else 0.0
    distinct_local_extrema = sum(
        (z[i]-z[i-1])*(z[i+1]-z[i]) < 0 and
        abs(z[i] - 0.5*(z[i-1]+z[i+1])) > max(0.35, relief*0.0025)
        for i in range(1, len(z)-1))
    errors = []
    if relief / span < 0.16:
        errors.append("InsufficientMountainRelief")
    if turning < 5:
        errors.append("TerrainHasTooFewSlopeReversals")
    if active_curvature / max(1,len(curvature)) < 0.20:
        errors.append("TerrainIsExcessivelySmooth")
    if local_relief_fraction < 0.055:
        errors.append("TerrainLacksDrainageScaleRelief")
    if distinct_local_extrema < 5:
        errors.append("TerrainLacksDistinctLocalLandforms")
    # These shape thresholds exercise synthetic mountain fixtures. An observed
    # DEM slope need not contain a ridge, large relief, or five local extrema.
    # Keep shape diagnostics, but never reject/roughen DEM evidence to match them.
    shape_findings = list(errors)
    if not synthetic_test_only:
        errors = []
    return {"policyId":("ADV2-NATURAL-TERRAIN-TEXTURE-QA-1.0" if synthetic_test_only
                        else "ADV2-DEM-PROFILE-DIAGNOSTIC-1.0"), "passed":not errors,
            "errors":errors, "sampleCount":len(x), "reliefToSpan":relief/span,
            "shapeGateApplicable":bool(synthetic_test_only),
            "shapeDiagnostics":shape_findings,
            "demResolutionVerifiedByThisAudit":False,
            "slopeTurningCount":turning,
            "activeCurvatureFraction":active_curvature/max(1,len(curvature)),
            "localResidualReliefM":local_relief,
            "localResidualReliefFraction":local_relief_fraction,
            "distinctLocalExtremaCount":distinct_local_extrema,
            "syntheticTestOnly":bool(synthetic_test_only),
            "demEvidenceClaim":not bool(synthetic_test_only)}
