"""Advanced-V2-only contact geometry and explicit model-lower-limit policy.

This module changes a broad synthetic prior, not observed geology.  It uses a
Matérn-3/2 covariance for layer-specific positive-thickness variability because
the former long-wave harmonic contacts were visually over-smooth.  It never
derives subsurface geometry from the modern terrain and never adds independent
free-form contact curves: every contact remains the shared boundary produced by
stacking positive thickness fields.
"""
from __future__ import annotations

import math
import numpy as np


POLICY_ID = "ADV2-MATERN32-CONTACT-CLASS-SHARED-THICKNESS-2.0"

CONTACT_CLASS_RANGES = {
    # These are scale-relative synthetic display priors, not measured regional
    # roughness.  Local geological events must use their own evidence-gated
    # geometry and are rejected by this broad-background policy.
    "WeatheringFront": {"longFraction": 0.18, "shortFraction": 0.040},
    "ConformableDepositional": {"longFraction": 0.28, "shortFraction": 0.075},
    "RockMassStateTransition": {"longFraction": 0.22, "shortFraction": 0.055},
    "InferredCoverBedrockContact": {"longFraction": 0.28, "shortFraction": 0.075},
}


def _contact_class(architecture_type: str | None, index: int, count: int) -> str:
    if index == count - 1:
        return "ModelCutoff"
    if architecture_type == "PlutonicWeatheringMass":
        return "WeatheringFront" if index == 0 else "RockMassStateTransition"
    return "WeatheringFront" if index == 0 else "ConformableDepositional"


def audit_plutonic_depth_dependent_parallelism(model: dict) -> dict:
    """Require progressively non-copy-like fronts with depth in plutonic rock.

    This is a synthetic portrayal gate, not a universal weathering-depth law.
    It permits shallow topographic control while preventing every deeper rock-
    mass state boundary from becoming a simple translated terrain copy.
    """
    architecture = (model.get("regionalPriorProfile") or {}).get(
        "backgroundArchitecture", {}).get("architectureType")
    if architecture != "PlutonicWeatheringMass":
        return {"applicable": False, "passed": True, "errors": [], "findings": []}
    terrain = np.asarray(model.get("terrainElevationM", []), dtype=float)
    layers = model.get("composition", {}).get("layersTopDown", [])
    relief = float(np.ptp(terrain))
    if terrain.size < 3 or relief <= 0:
        return {"applicable": True, "passed": False,
                "errors": ["TerrainUnavailableForPlutonicParallelismAudit"], "findings": []}
    errors, findings = [], []
    for index, row in enumerate(layers[:-1]):
        contact = np.asarray(row.get("bottomElevationM", []), dtype=float)
        if contact.shape != terrain.shape or not np.isfinite(contact).all():
            errors.append(f"InvalidPlutonicContact:{row.get('unitId')}")
            continue
        residual = float(np.ptp(contact - terrain) / relief)
        minimum = 0.0 if index < 2 else 0.015 * (index - 1)
        passed = residual + 1e-12 >= minimum
        if not passed:
            errors.append(f"PlutonicFrontTooTerrainParallel:{row.get('unitId')}")
        findings.append({"unitId": row.get("unitId"), "depthOrder": index,
                         "contactClass": row.get("bottomContactClass"),
                         "terrainContactCorrelation": float(np.corrcoef(terrain, contact)[0, 1]),
                         "relativeResidualRelief": residual,
                         "minimumRelativeResidualRelief": minimum, "passed": passed})
    return {"schemaVersion": "PlutonicDepthParallelismAudit-1.0",
            "applicable": True, "basisType": "SyntheticPortrayalGate",
            "passed": not errors, "errors": errors, "findings": findings}


def _matern32_sample(stations, *, seed: int, range_m: float) -> np.ndarray:
    """Return one standardized Matérn-3/2 realization on arbitrary stations.

    k(d) = (1 + sqrt(3)d/l) exp(-sqrt(3)d/l)

    ``range_m`` is the covariance length scale ``l`` in metres.  The output is
    standardized empirically so amplitude is controlled separately in log
    thickness space.  This is a numerical prior, not geological evidence.
    """
    x = np.asarray(stations, dtype=float)
    if x.ndim != 1 or x.size < 5 or not np.isfinite(x).all() or np.any(np.diff(x) <= 0):
        raise ValueError("ordered finite stations are required")
    if not math.isfinite(range_m) or range_m <= 0:
        raise ValueError("positive finite Matérn range is required")
    distance = np.abs(x[:, None] - x[None, :])
    scaled = math.sqrt(3.0) * distance / float(range_m)
    covariance = (1.0 + scaled) * np.exp(-scaled)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    tolerance = np.finfo(float).eps * x.size * 64.0
    if float(eigenvalues.min()) < -tolerance:
        raise ValueError("Matérn covariance is not positive semidefinite")
    root = eigenvectors @ np.diag(np.sqrt(np.maximum(eigenvalues, 0.0)))
    values = root @ np.random.default_rng(int(seed)).standard_normal(x.size)
    values -= float(values.mean())
    scale = float(values.std())
    if scale <= np.finfo(float).eps:
        raise ValueError("degenerate Matérn realization")
    return values / scale


def _layer_thickness(stations, mean_m: float, *, seed: int, span_m: float,
                     log_std: float, long_fraction: float, short_fraction: float) -> np.ndarray:
    if not math.isfinite(mean_m) or mean_m <= 0:
        raise ValueError("positive finite mean thickness is required")
    if not math.isfinite(log_std) or not 0 < log_std <= 0.6:
        raise ValueError("log-thickness standard deviation is outside the Advanced V2 bound")
    long = _matern32_sample(stations, seed=seed, range_m=max(span_m * long_fraction, 20.0))
    short = _matern32_sample(stations, seed=seed + 104729,
                             range_m=max(span_m * short_fraction, 10.0))
    latent = log_std * (0.82 * long + 0.38 * short)
    thickness = np.exp(latent)
    thickness *= mean_m / float(thickness.mean())
    # Hard bounds prevent a visual roughness setting from creating vanishing or
    # implausibly dominant units in this conservative no-local-event prior.
    return np.clip(thickness, mean_m * 0.22, mean_m * 2.4)


def apply_advanced_contact_geometry(model: dict) -> dict:
    """Apply the Advanced V2 broad-prior contact policy in place.

    The operation is deliberately limited to a conservative background stack.
    Explicit erosion, fault, intrusion, lens or observed-contact geometry must
    retain its event-specific implementation and is therefore rejected here.
    """
    architecture = model.get("syntheticEventArchitecture", {})
    if architecture.get("architectureMode") != "ConservativeRegionalPrior_NoLocalizedEvents":
        raise ValueError("Advanced broad contact policy is out of scope for localized events")
    layers = model.get("composition", {}).get("layersTopDown", [])
    bodies = architecture.get("renderBodies", [])
    stations = np.asarray(model.get("stationsM", []), dtype=float)
    terrain = np.asarray(model.get("terrainElevationM", []), dtype=float)
    if len(layers) < 3 or len(bodies) != len(layers) or terrain.shape != stations.shape:
        raise ValueError("complete conservative layer stack is required")
    if [row.get("unitId") for row in layers] != [row.get("unitId") for row in bodies]:
        raise ValueError("composition and render-body orders disagree")
    span = float(np.ptp(stations))
    if span <= 0 or not np.isfinite(terrain).all():
        raise ValueError("finite terrain and nonzero section span are required")

    # Parameters are dimensioned by the section span and recorded in output.
    regional_profile = model.get("regionalPriorProfile") or {}
    background = regional_profile.get("backgroundArchitecture") or {}
    default_log_std = float(background.get("defaultLogStd", 0.24))
    if not 0 < default_log_std <= 0.6:
        raise ValueError("regional broad-prior log thickness standard deviation is invalid")
    terrain_conditioning = regional_profile.get("terrainConditioning") or {}
    terrain_class = terrain_conditioning.get("terrainClass", "Unresolved")
    architecture_type = background.get("architectureType")
    domain = model.get("lithologySelection", {}).get("domain")
    # Volcanic surface cover includes soil, primary tephra and the thin
    # paleosol/reworked-tephra marker.  Letting the marker participate in the
    # deep structural clipping previously inflated a declared 3 m horizon to
    # more than 50 m where an overlying package pinched out.
    has_volcanic_marker = len(layers) > 2 and layers[2].get("unitId") == "SYN-PALEOSOL-TEPHRA"
    protected_cover_count = (3 if domain == "VolcanicTerrain" and has_volcanic_marker else
        2 if domain == "VolcanicTerrain" else
        2 if domain == "MetamorphicBelt" else 1)
    truncation_classes = {"RollingHills", "MountainousRelief", "NarrowValleyOrGorge",
                          "MountainFrontPiedmont", "ArtificiallyModifiedOrUnresolved"}
    use_erosional_truncation = terrain_class in truncation_classes and \
        architecture_type != "PlutonicWeatheringMass"
    policy = {
        "policyId": POLICY_ID,
        "basisType": "SyntheticAssumption",
        "algorithmSourceReference": "RasmussenWilliams2006_GPML_Chapter4_MaternCovariance",
        "algorithmBasisType": "IndependentImplementationFromPublishedEquation",
        "geologicalValidityClaim": "None_NumericalPriorOnly",
        "terrainInputAcceptedByThicknessSampler": False,
        "contactConstruction": "SequentialPositiveThickness_ExactSharedBoundaries",
        "contactClassRangePolicy": CONTACT_CLASS_RANGES,
        "defaultLogThicknessStd": default_log_std,
        "terrainConditioning": terrain_conditioning,
        "protectedTerrainFollowingCoverCount": protected_cover_count,
        "geometryMode": ("ErosionalTruncationOfIndependentStructuralContacts"
                         if use_erosional_truncation else
                         "SequentialPositiveThickness_ExactSharedBoundaries"),
    }
    top = terrain.copy()
    structural_reference = float(np.median(terrain))
    structural_depth = 0.0
    facies_metadata = {row.get("unitId"): row for row in regional_profile.get("faciesMetadata", [])}
    rebuilt_layers = []
    rebuilt_bodies = []
    for index, (source, body) in enumerate(zip(layers, bodies)):
        source_mean = float(np.mean(np.asarray(source["thicknessM"], dtype=float)))
        declared = facies_metadata.get(source.get("unitId"), {}).get("declaredMeanThicknessM")
        # The evidence-bounded facies palette declares the intended scale of
        # every synthetic package.  The upstream generic stack redistributes
        # thickness to fill its display domain, so reusing its derived mean can
        # erase thin marker horizons and create implausibly thick bands.
        mean = (float(declared) if declared is not None and index < len(layers)-1
                else source_mean)
        contact_class = _contact_class(architecture_type, index, len(layers))
        if contact_class == "ModelCutoff":
            # Preserve the deepest generated boundary. The drafting contract
            # may continue this same unit to its rounded frame, but must never
            # invent a different basement lithology at this cutoff.
            thickness = np.asarray(source["thicknessM"], dtype=float)
            if thickness.shape != stations.shape or not np.isfinite(thickness).all() or np.any(thickness <= 0):
                raise ValueError("positive finite display-base thickness is required")
            bottom = top - thickness
            range_record = None
        elif use_erosional_truncation and index >= protected_cover_count:
            range_policy = CONTACT_CLASS_RANGES[contact_class]
            structural_depth += mean
            centered_station = stations - float(np.mean(stations))
            dip_degrees = float(background.get("regionalDipDegrees", 0.0))
            tilt = math.tan(math.radians(dip_degrees)) * centered_station
            relief = _matern32_sample(
                stations, seed=int(model["seed"]) + 91009 + index * 2017,
                range_m=max(span * range_policy["longFraction"], 20.0)) * mean * 0.55
            candidate = structural_reference - structural_depth + tilt + relief
            bottom = np.minimum(top, candidate)
            thickness = top - bottom
            range_record = {
                "longRangeM": max(span * range_policy["longFraction"], 20.0),
                "shortRangeM": None, **range_policy,
                "construction":"IndependentStructuralSurfaceClippedByOverlyingBoundary",
            }
        else:
            range_policy = CONTACT_CLASS_RANGES[contact_class]
            layer_log_std = 0.10 if index == 0 else policy["defaultLogThicknessStd"]
            thickness = _layer_thickness(
                stations, mean, seed=int(model["seed"]) + 81013 + index * 1009,
                span_m=span, log_std=layer_log_std,
                long_fraction=range_policy["longFraction"],
                short_fraction=range_policy["shortFraction"],
            )
            bottom = top - thickness
            range_record = {
                "longRangeM": max(span * range_policy["longFraction"], 20.0),
                "shortRangeM": max(span * range_policy["shortFraction"], 10.0),
                **range_policy,
            }
        active = [bool(value > 1e-9) for value in thickness]
        common = {"topElevationM": top.tolist(), "bottomElevationM": bottom.tolist(),
                  "thicknessM": thickness.tolist(), "activeMask": active,
                  "allowPinchout": bool(use_erosional_truncation and index > 0),
                  "bottomContactClass": contact_class,
                  "bottomContactRange": range_record}
        rebuilt_layers.append({**source, **common})
        rebuilt_bodies.append({**body, **common})
        top = bottom

    model["composition"]["layersTopDown"] = rebuilt_layers
    architecture["renderBodies"] = rebuilt_bodies
    architecture["advancedContactGeometry"] = policy
    model["advancedContactGeometry"] = policy
    lower_boundary = rebuilt_layers[-1]["bottomElevationM"]
    model["modelDomain"] = {
        "lowerBoundaryElevationM": lower_boundary,
        "minimumGeologicalElevationM": float(min(lower_boundary)),
        "lowerLimitClass": "VariableSyntheticModelBoundary",
        "belowLimitStatus": "SyntheticBasalContinuationEligible",
        "lowerLimitIsGeologicalContact": False,
        "displayBaseUnitId": rebuilt_layers[-1]["unitId"],
    }
    model["deepBodyRole"] = "SyntheticUnclassifiedDisplayBaseToExplicitModelLimit"
    return model


def audit_advanced_contact_geometry(model: dict) -> dict:
    """Check domain closure, shared contacts and scale-aware shape diversity."""
    layers = model.get("composition", {}).get("layersTopDown", [])
    stations = np.asarray(model.get("stationsM", []), dtype=float)
    errors = []
    findings = []
    if len(layers) < 3 or stations.size < 5:
        return {"passed": False, "errors": ["IncompleteAdvancedContactGeometry"]}
    spacing = float(np.median(np.diff(stations)))
    for index, row in enumerate(layers):
        top = np.asarray(row.get("topElevationM", []), dtype=float)
        bottom = np.asarray(row.get("bottomElevationM", []), dtype=float)
        thickness = np.asarray(row.get("thicknessM", []), dtype=float)
        if top.shape != stations.shape or bottom.shape != stations.shape or thickness.shape != stations.shape:
            errors.append(f"InvalidLayerShape:{index}")
            continue
        allow_pinchout = bool(row.get("allowPinchout"))
        invalid_thickness = np.any(thickness < -1e-12) if allow_pinchout else np.any(thickness <= 0)
        if not np.isfinite(np.r_[top, bottom, thickness]).all() or invalid_thickness:
            errors.append(f"NonPositiveOrNonFiniteThickness:{index}")
        if not np.allclose(top - bottom, thickness, rtol=0, atol=1e-9):
            errors.append(f"ThicknessIdentityMismatch:{index}")
        if index + 1 < len(layers):
            next_top = np.asarray(layers[index + 1].get("topElevationM", []), dtype=float)
            if not np.array_equal(bottom, next_top):
                errors.append(f"UnsharedContact:{index}")
        if index < len(layers) - 1:
            slope = np.gradient(bottom, stations)
            second = np.gradient(slope, stations)
            curvature = second / np.power(1.0 + slope * slope, 1.5)
            normalized_q95 = float(np.quantile(np.abs(curvature) * spacing, 0.95))
            turning_points = int(np.count_nonzero(np.diff(np.sign(np.diff(bottom))) != 0))
            findings.append({"unitId": row["unitId"],
                             "contactClass": row.get("bottomContactClass"),
                             "rangePolicy": row.get("bottomContactRange"),
                             "normalizedCurvatureQ95": normalized_q95,
                             "turningPointCount": turning_points})
            contact_class = row.get("bottomContactClass")
            ranges = row.get("bottomContactRange")
            if contact_class not in CONTACT_CLASS_RANGES or not isinstance(ranges, dict):
                errors.append(f"ContactClassRangeMissing:{index}")
            elif (ranges.get("longFraction") != CONTACT_CLASS_RANGES[contact_class]["longFraction"] or
                  ranges.get("shortFraction") != CONTACT_CLASS_RANGES[contact_class]["shortFraction"]):
                errors.append(f"ContactClassRangeMismatch:{index}")
    domain = model.get("modelDomain", {})
    deepest = np.asarray(layers[-1].get("bottomElevationM", []), dtype=float)
    if domain.get("lowerLimitClass") != "VariableSyntheticModelBoundary" or \
       domain.get("belowLimitStatus") != "SyntheticBasalContinuationEligible":
        errors.append("ModelLowerLimitSemanticsMissing")
    declared = np.asarray(domain.get("lowerBoundaryElevationM", []), dtype=float)
    if deepest.size and (declared.shape != deepest.shape or not np.array_equal(deepest, declared)):
        errors.append("DisplayBaseDoesNotReachModelLowerLimit")
    # This is a portfolio-prior diversity check, not a universal law.  A fully
    # evidence-controlled planar succession may explicitly opt out upstream.
    required_turns = 1 if stations.size < 9 else 2
    diverse = sum(row["turningPointCount"] >= required_turns and row["normalizedCurvatureQ95"] > 1e-5
                  for row in findings)
    if diverse < max(1, len(findings) // 2):
        errors.append("SyntheticPriorContactsExcessivelySmooth")
    plutonic_parallelism = audit_plutonic_depth_dependent_parallelism(model)
    errors.extend(plutonic_parallelism["errors"])
    return {"passed": not errors, "errors": errors, "policyId": POLICY_ID,
            "evaluatedContactCount": len(findings), "shapeDiverseContactCount": diverse,
            "minimumTurningPointsPerDiverseContact": required_turns,
            "stationCount": int(stations.size),
            "findings": findings,
            "plutonicDepthDependentParallelismAudit": plutonic_parallelism,
            "checkedBeforeOutput": True}


def audit_contact_sampler_implementation() -> dict:
    """Run the existing 500 m/51-station regression, not a route acceptance test.

    A finite Monte Carlo contrast changes with sample count/spacing. Its fixed
    0.04 regression margin cannot diagnose a particular section's geometry.
    Keep the established fixture/seeds and rejection threshold unchanged.
    Per-section geometry and range metadata are checked by the separate audit.
    """
    result = audit_contact_range_ensemble([float(i*10) for i in range(51)], seed_count=24)
    result.update(evaluationScope="ImplementationRegression_NotRouteGeometry",
                  referenceGrid={"spanM":500.0,"stationCount":51,"spacingM":10.0},
                  routeGeometryAcceptanceClaim=False)
    return result


def audit_contact_range_ensemble(stations, *, seed_count: int = 64) -> dict:
    """Empirically distinguish declared contact scales over multiple seeds.

    This is a numerical implementation audit, not an estimate of regional
    geological roughness.  It guards against merely recording different range
    values while accidentally generating statistically identical contacts.
    """
    x = np.asarray(stations, dtype=float)
    if isinstance(seed_count, bool) or not isinstance(seed_count, int) or seed_count < 16:
        raise ValueError("at least 16 ensemble seeds are required")
    if x.ndim != 1 or x.size < 5 or np.any(np.diff(x) <= 0):
        raise ValueError("at least five ordered stations are required")
    span = float(np.ptp(x))
    spacing = float(np.median(np.diff(x)))
    lag_steps = max(1, int(round((span * 0.10) / spacing)))
    lag_m = float(np.median(x[lag_steps:] - x[:-lag_steps]))
    results = {}
    for class_index, (contact_class, policy) in enumerate(CONTACT_CLASS_RANGES.items()):
        scale = max(span * policy["longFraction"], 20.0)
        correlations = []
        for index in range(seed_count):
            values = _matern32_sample(x, seed=700001 + class_index * 100003 + index,
                                      range_m=scale)
            correlations.append(float(np.mean(values[:-lag_steps] * values[lag_steps:])))
        theoretical = float((1.0 + math.sqrt(3.0) * lag_m / scale) *
                            math.exp(-math.sqrt(3.0) * lag_m / scale))
        results[contact_class] = {
            "declaredLongRangeM": scale, "evaluationLagM": lag_m,
            "empiricalMeanCorrelation": float(np.mean(correlations)),
            "empiricalStdCorrelation": float(np.std(correlations)),
            "unstandardizedTheoreticalCorrelation": theoretical,
            "seedCount": seed_count,
        }
    weathering = results["WeatheringFront"]["empiricalMeanCorrelation"]
    conformable = results["ConformableDepositional"]["empiricalMeanCorrelation"]
    errors = []
    if conformable <= weathering + 0.04:
        errors.append("ContactClassesNotEmpiricallyDistinguishable")
    if any(not math.isfinite(row["empiricalMeanCorrelation"]) for row in results.values()):
        errors.append("NonFiniteEmpiricalCorrelation")
    return {"passed": not errors, "errors": errors,
            "policyId": "ADV2-CONTACT-RANGE-MULTISEED-AUDIT-1.0",
            "basisType": "NumericalImplementationAudit",
            "geologicalValidityClaim": "None", "results": results}
