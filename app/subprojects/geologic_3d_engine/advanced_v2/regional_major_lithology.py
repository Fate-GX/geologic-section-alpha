"""Evidence-gated major Japanese lithology specialization.

Mapped surface lithology may select a compatible broad rock name.  It never
becomes a measured subsurface contact or a depth-only rock-type inference.
"""
from __future__ import annotations

import copy


POLICY_ID = "ADV2-REGIONAL-MAJOR-LITHOLOGY-1.0"

# Compatibility exports; the maintained vocabulary lives in a reloadable JSON.
from regional_lithology_data import load_vocabulary, regional_dataset_for_plan
_VOCABULARY = load_vocabulary()
MAJOR_LITHOLOGIES = {r["key"]:{**r, "domains":set(r["domains"])} for r in _VOCABULARY["lithologies"]}
SPECIFICITY_ORDER = tuple(_VOCABULARY["specificityOrder"])


def resolve_major_lithology_evidence(plan: dict, domain: str) -> dict:
    data = regional_dataset_for_plan(plan)
    vocabulary = load_vocabulary()
    by_key = {r["key"]:r for r in vocabulary["lithologies"]}
    eligible = [c for c in data["candidates"] if domain in c["domains"]]
    ranked = sorted(({"key":c["key"], "count":c["onRouteCount"]+c["nearbyCount"],
                      "ja":c["labelJa"], "en":c["labelEn"], "domains":c["domains"],
                      "sourceRecordIds":c["recordIds"], "onRouteCount":c["onRouteCount"],
                      "nearbyCount":c["nearbyCount"], "matchedAliases":by_key[c["key"]]["aliases"]}
                     for c in eligible), key=lambda r:(-r["onRouteCount"], -r["count"], r["key"]))
    sample_count = sum(r["origin"]=="OnRoute" for r in data["records"])
    matched = len({rid for c in ranked for rid in c["sourceRecordIds"] if rid.startswith("OnRoute-")})
    # selectedKey is only a backwards-compatible display preference, not a filter.
    dominant = ranked[0] if ranked else None
    return {"policyId":"ADV2-REGIONAL-MAJOR-LITHOLOGY-2.0", "domain":domain,
            "sampleCount":sample_count, "matchedSampleCount":matched,
            "matchedCoverage":matched/sample_count if sample_count else 0.0,
            "dominantFraction":dominant["onRouteCount"]/sample_count if dominant and sample_count else 0.0,
            "rankedCandidates":ranked, "selectedKeys":[r["key"] for r in ranked],
            "selectedKey":dominant["key"] if dominant else None,
            "selectedLabelJa":dominant["ja"] if dominant else None,
            "selectionThreshold":None, "majorityOnlyFiltering":False,
            "regionalInputId":data["datasetId"], "vocabularySha256":data["vocabularySha256"],
            "subsurfaceContactAuthorized":False,
            "status":"MultipleMappedMembersRetained" if len(ranked)>1 else
                     "SpecificMappedLithologyPrior" if ranked else "BroadDomainPrior_NoSpecificRockSelected"}


def specialize_domain_rows(rows: list[tuple], domain: str, evidence: dict) -> list[tuple]:
    """Apply data-defined member groups without adding unsupported contacts."""
    from regional_lithology_data import composite_specializations
    replacements = composite_specializations(domain, evidence)
    return [(r[0], replacements.get(r[0], {}).get("ja", r[1]), *r[2:]) for r in rows]


def specialized_english_labels(domain: str, evidence: dict) -> dict[str, str]:
    from regional_lithology_data import composite_specializations
    return {key:spec["en"] for key,spec in composite_specializations(domain, evidence).items()}


def burial_conditioning_metadata(rows: list[tuple], domain: str) -> list[dict]:
    """Describe consolidation tendency separately from lithology and hardness."""
    total = sum(max(0.0, float(row[2])) for row in rows) or 1.0
    cumulative = 0.0
    output = []
    rock_domains = {"VolcanicTerrain", "SedimentaryRockTerrain", "PlutonicTerrain",
                    "AccretionaryComplex", "MetamorphicBelt"}
    for row in rows:
        thickness = max(0.0, float(row[2]))
        midpoint = cumulative + thickness * 0.5
        fraction = midpoint / total
        if domain in rock_domains:
            state = "RockMass_WeatheringAndFractureStateRequired"
        elif fraction < 0.20:
            state = "ShallowUnconsolidatedPrior"
        elif fraction < 0.65:
            state = "BurialCompactionTendencyPrior"
        else:
            state = "DeeperCompactedOrLithifiedCandidate_Unverified"
        output.append({
            "unitId": row[0], "relativeMidBurialDepth": fraction,
            "conditioningState": state,
            "hardnessDerivedFromDepth": False,
            "numericalCompactionApplied": False,
            "reason": "Depth conditions consolidation state; it does not select rock type or hardness.",
        })
        cumulative += thickness
    return output


def audit_effective_lithology_diversity(domain: str, evidence: dict,
                                        rows: list[tuple]) -> dict:
    """Do not count weathering/fracture states as separate parent lithologies."""
    parent_keys = [row["key"] for row in evidence.get("rankedCandidates", [])
                   if row.get("count", 0) > 0]
    state_roles = {"WeatheringState", "FractureState", "FreshRock", "SurfaceCover"}
    state_count = sum(row[4] in state_roles for row in rows)
    parent_count = len(set(parent_keys))
    if domain == "PlutonicTerrain" and parent_count <= 1:
        status = "SingleParentLithology_WeatheringStatesNotCountedAsLithologyDiversity"
        diverse_claim_allowed = False
    else:
        status = "MultipleEvidenceMatchedParents" if parent_count > 1 else "BroadPriorOnly"
        diverse_claim_allowed = parent_count > 1
    return {
        "policyId":"ADV2-EFFECTIVE-LITHOLOGY-DIVERSITY-1.0",
        "domain":domain,
        "parentLithologyKeys":sorted(set(parent_keys)),
        "parentLithologyCount":parent_count,
        "weatheringOrStateUnitCount":state_count,
        "geometricBodyCount":len(rows),
        "weatheringStatesCountAsDistinctLithologies":False,
        "lithologyDiversityClaimAllowed":diverse_claim_allowed,
        "portfolioDiversityPassed":diverse_claim_allowed,
        "geologicalSingleParentModelAllowed":True,
        "status":status,
        "passed":True,
        "note":"A geologically valid single-parent rock mass is allowed, but must not be advertised as lithologically diverse.",
    }
