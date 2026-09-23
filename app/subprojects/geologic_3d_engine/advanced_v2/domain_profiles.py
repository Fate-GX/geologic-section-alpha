"""Advanced-only broad priors for domains absent from the frozen basic v1."""
from __future__ import annotations
import copy

UNCONSOLIDATED_PROFILE = {
    "profileId": "ADV2-JP-UNCONSOLIDATED-BROAD-PRIOR-1.0",
    "scope": "Domain", "basisType": "SyntheticAssumption",
    "geologicalProvince": None,
    "ageInterval": "QuaternaryOrUnresolvedYoungDeposit",
    "environment": "UnresolvedDepositionalLowland",
    "eventAuthorization": {"status": "NoRouteApplicableSubsurfaceEvidence",
        "requestedLocalizedEventTypes": [], "routeApplicableSubsurfaceSourceIds": []},
    "backgroundArchitecture": {"architectureType": "DeformedSedimentaryStack",
        "regionalDipDegrees": 0.6, "defaultCorrelationRangeM": 180.0,
        "defaultLogStd": 0.22,
        "meaning": "Broad heterogeneous unconsolidated succession only"},
    "substrateFacies": [
        ["ADV2-SURFACE-SOIL", "表土・人工改変の可能性を含む表層（推定）", 1.2, "#9b805e"],
        ["ADV2-FINE-SEDIMENT", "粘土・シルト質堆積物（推定）", 5.0, "#9da7a0"],
        ["ADV2-SAND", "砂質堆積物（推定）", 7.0, "#d6bd76"],
        ["ADV2-GRAVEL", "砂れき（推定）", 9.0, "#aa8564"],
        ["ADV2-OLDER-SEDIMENT", "更新統または下位の堆積物（推定）", 20.0, "#7f8985"],
        ["ADV2-DISPLAY-BASE", "地質基盤・表示基底（未特定）", 75.0, "#666866"]],
    "englishUnitLabels": {
        "ADV2-SURFACE-SOIL": "Surface soil / possibly modified ground (inferred)",
        "ADV2-FINE-SEDIMENT": "Clay- and silt-rich sediment (inferred)",
        "ADV2-SAND": "Sand-rich sediment (inferred)",
        "ADV2-GRAVEL": "Sand and gravel sediment (inferred)",
        "ADV2-OLDER-SEDIMENT": "Older sedimentary succession (inferred)",
        "ADV2-DISPLAY-BASE": "Unclassified display base",
    },
    "limitations": ["Mapped surface class does not determine the vertical sequence",
        "Depositional environment is unresolved without boreholes or sections",
        "No local channel, buried valley or fault is authorized"]}

def profile_for_domain(domain: str):
    return copy.deepcopy(UNCONSOLIDATED_PROFILE) if domain == "UnconsolidatedSedimentTerrain" else None


def contextual_profile_for_domain(domain: str, selected_domain_model: dict):
    """Bind a reusable core prior to explicit surrounding-inference metadata."""
    if domain == "UnconsolidatedSedimentTerrain":
        result = profile_for_domain(domain)
    elif domain in {"VolcanicTerrain", "SedimentaryRockTerrain", "AccretionaryComplex",
                    "PlutonicTerrain", "MetamorphicBelt"} and \
            selected_domain_model.get("facies"):
        result = {"profileId":f"ADV2-JP-CONTEXT-{domain}-1.0", "scope":"Domain",
            "basisType":"SyntheticAssumption", "geologicalProvince":None,
            "ageInterval":"Unresolved", "environment":"SurroundingMappedDomainPrior",
            "eventAuthorization":{"status":"NoRouteApplicableSubsurfaceEvidence",
                "requestedLocalizedEventTypes":[], "routeApplicableSubsurfaceSourceIds":[]},
            "backgroundArchitecture":{"architectureType":selected_domain_model["architectureType"],
                "meaning":"Surrounding-domain prior; no local structure authorized"},
            "substrateFacies":copy.deepcopy(selected_domain_model["facies"])}
    else:
        return None
    result["contextInference"] = {"inferredDomain":domain,
        "meaning":"Surrounding mapped geology estimate, not observed local subsurface"}
    return result


def broad_profile_for_domain(domain: str, selected_domain_model: dict):
    """Create a broad prior without claiming surrounding-site inference."""
    result = contextual_profile_for_domain(domain, selected_domain_model)
    if result is not None:
        result.pop("contextInference", None)
        result["profileId"] = f"ADV2-JP-BROAD-{domain}-1.0"
        result["environment"] = "MappedDomainBroadPrior"
    return result
