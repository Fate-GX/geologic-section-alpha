"""Advanced GSJ vocabulary coverage without changing the frozen v1 classifier."""
from __future__ import annotations
import math
from context_inference import context_evidence_from_plan

GSJ_UNCONSOLIDATED_TERMS = (
    "terrace deposit", "fan deposit", "natural levee", "delta deposit",
    "dune deposit", "beach deposit", "floodplain deposit", "talus deposit",
    "fan, talus", "glacial deposit",
    "段丘堆積", "扇状地堆積", "扇状地・崖錐", "自然堤防", "三角州堆積", "砂丘堆積", "浜堆積")


def advanced_legend_domain(legend: dict, frozen_classifier) -> str:
    original = frozen_classifier(legend)
    if original != "Unresolved":
        return original
    text = " ".join(str(legend.get(key, "")) for key in
                    ("title", "lithology_ja", "lithology_en",
                     "formationAge_ja", "formationAge_en")).casefold()
    if any(term.casefold() in text for term in GSJ_UNCONSOLIDATED_TERMS):
        return "UnconsolidatedSedimentTerrain"
    # GSJ English legends sometimes describe young deposits only as a marine /
    # non-marine "sediments" mixture.  Limit this fallback to Quaternary age
    # wording so older sedimentary rocks are not silently reclassified.
    if "quaternary" in text and "sediment" in text:
        return "UnconsolidatedSedimentTerrain"
    return "Unresolved"


def classify_plan_advanced(plan: dict, frozen_classifier, *, dominance_threshold=.65) -> dict:
    evidence = context_evidence_from_plan(
        plan, lambda legend: advanced_legend_domain(legend, frozen_classifier))
    total = evidence["routeLengthM"]
    scores = {}
    for row in evidence["sampleEvidence"]:
        key = row["classifiedDomain"]
        scores[key] = scores.get(key, 0.0) + row["weightM"]
    fractions = {key:value/total for key,value in scores.items()}
    ranked = sorted(fractions, key=lambda key:(-fractions[key], key))
    dominant = ranked[0]
    natural = [value for key,value in fractions.items() if key != "Unresolved" and value > 0]
    domain = (dominant if dominant != "Unresolved" and fractions[dominant] >= dominance_threshold else
              "MixedGeologicalDomain" if len(natural) > 1 else "Unresolved")
    valid_elevations = [float(row["elevationM"]) for row in plan.get("terrainProfile", [])
                        if isinstance(row.get("elevationM"), (int, float)) and
                        math.isfinite(float(row["elevationM"]))]
    relief = max(valid_elevations)-min(valid_elevations) if valid_elevations else None
    grade = relief/total if relief is not None else None
    landform = ("UnknownRelief" if relief is None else "MountainousRelief" if relief >= 100 or grade >= .12
                else "HillyRelief" if relief >= 30 or grade >= .04 else "LowRelief")
    source = plan.get("surfaceGeology", {})
    return {"schemaVersion":"AdvancedPlanGeologicalDomainClassification-2.0",
            "geologicalDomain":domain, "dominantMappedDomain":dominant,
            "domainFractionsByRouteLength":fractions,
            "dominanceThreshold":dominance_threshold, "landformContext":landform,
            "terrainReliefM":relief, "routeLengthM":total,
            "terrainDeterminedGeologicalDomain":False,
            "primaryEvidence":"MappedSurfaceGeology",
            "sourceId":source.get("sourceId"), "sourceEdition":source.get("sourceEdition"),
            "sampleEvidence":evidence["sampleEvidence"],
            "vocabularyExtension":"AdvancedGSJBroadDomainVocabulary-2.0",
            "subsurfaceMeaning":"PriorSelectorOnly_NotSubsurfaceObservation",
            "passed":domain != "Unresolved"}
