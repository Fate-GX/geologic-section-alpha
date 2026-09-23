"""Mandatory universal-first geological prior gate.

The gate separates hard geological invariants from regional interpretations.
It intentionally runs before any stochastic geometry is sampled.
"""
from __future__ import annotations

UNIVERSAL_POLICY_ID = "UniversalGeologicalPlausibilityGate-1.0"

HARD_INVARIANTS = (
    "NoUnexplainedMaterialOverlapOrVoid",
    "PositiveThicknessOrExplicitPinchout",
    "YoungerEventsCannotBeTruncatedByOlderEvents",
    "TerrainDoesNotDetermineSubsurfaceGeometry",
    "MappedSurfaceUnitDoesNotAuthorizeVerticalProjection",
    "LocalizedMajorEventRequiresRouteApplicableEvidence",
)

LOCALIZED_EVENT_TYPES = {"IncisedValley", "Fault", "Fold", "Intrusion", "Lens"}


def evaluate_geological_priors(regional_profile: dict | None) -> dict:
    """Resolve architecture in the immutable order universal -> regional.

    A regional profile may narrow the universal rules.  It cannot relax a hard
    invariant.  Localized events require explicit route-applicable source IDs;
    a regional name or mapped surface class is insufficient.
    """
    universal = {"policyId": UNIVERSAL_POLICY_ID,
                 "hardInvariants": list(HARD_INVARIANTS), "passed": True}
    if regional_profile is None:
        return {"passed": True, "evaluationOrder": ["Universal", "UnscopedSynthetic"],
                "universal": universal, "regional": None,
                "architectureMode": "UnscopedSyntheticDiagnostic",
                "localizedEventsAuthorized": True,
                "realRegionAuthorized": False}

    profile_id = regional_profile.get("profileId")
    authorization = regional_profile.get("eventAuthorization")
    errors = []
    if not isinstance(profile_id, str) or not profile_id:
        errors.append("MissingRegionalProfileId")
    if not isinstance(authorization, dict):
        errors.append("MissingRegionalEventAuthorization")
        authorization = {}
    requested = set(authorization.get("requestedLocalizedEventTypes", []))
    unknown = requested - LOCALIZED_EVENT_TYPES
    if unknown:
        errors.append("UnknownLocalizedEventType:" + ",".join(sorted(unknown)))
    sources = authorization.get("routeApplicableSubsurfaceSourceIds", [])
    evidence_bound = authorization.get("status") == "EvidenceBound"
    localized_authorized = bool(requested and evidence_bound and sources)
    if requested and not localized_authorized:
        errors.append("LocalizedEventRequestLacksRouteApplicableEvidence")
    mode = ("EvidenceBoundLocalizedEvents" if localized_authorized else
            "ConservativeRegionalPrior_NoLocalizedEvents")
    # Unsupported event requests cause safe degradation, not fabrication.
    return {"passed": not [e for e in errors if e.startswith("MissingRegional") or
                           e.startswith("UnknownLocalized")],
            "evaluationOrder": ["Universal", "Regional"],
            "universal": universal,
            "regional": {"profileId": profile_id, "authorization": authorization,
                         "findings": errors},
            "architectureMode": mode,
            "localizedEventsAuthorized": localized_authorized,
            "safeDegradationApplied": bool(requested and not localized_authorized),
            "realRegionAuthorized": False}
