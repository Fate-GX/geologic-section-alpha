"""Evidence-bounded broad-prior lithology selection for Advanced V2.

The selector increases descriptive diversity without inventing formation names.
Every added member remains a SyntheticAssumption unless an applicable typed
regional record explicitly supplies stronger evidence.
"""
from __future__ import annotations

import copy
from regional_lithology_data import (regional_dataset_for_plan, composite_specializations,
                                     selection_accounting)
from facies_architecture import plan_facies_architecture
from current_lithology_terminology import terminology_record, audit_publication_terminology
from regional_bedrock import resolve_regional_bedrock, has_ash_evidence
from regional_major_lithology import (resolve_major_lithology_evidence,
                                      specialize_domain_rows,
                                      specialized_english_labels,
                                      burial_conditioning_metadata,
                                      audit_effective_lithology_diversity)


POLICY_ID = "ADV2-EVIDENCE-BOUNDED-LITHOLOGY-SUBSET-1.0"

ENGLISH_LABELS = {
    "ADV2-SURFACE-SOIL": "Surface cover (inferred)",
    "ADV2-ORGANIC-FINE": "Organic-bearing clay and silt (inferred)",
    "ADV2-CLAY": "Clay-rich sediment (inferred)",
    "ADV2-SILT": "Silt-rich sediment (inferred)",
    "ADV2-SAND": "Sand-rich sediment (inferred)",
    "ADV2-GRAVELLY-SAND": "Gravelly sand (inferred)",
    "ADV2-GRAVEL": "Sand and gravel (inferred)",
    "ADV2-PEAT": "Peat and organic mud (inferred)",
    "ADV2-OLD-CLAY": "Stiff older clay (inferred)",
    "ADV2-OLDER-SEDIMENT": "Older sediment; display base (inferred)",
    "ADV2-OLD-SAND": "Older sand-dominant deposit (inferred)",
    "ADV2-OLD-GRAVEL": "Older gravel-dominant deposit (inferred)",
    "ADV2-OLD-SILT-CLAY": "Older silt and clay deposit (inferred)",
    "ADV2-OLD-VOLCANIC-ASH": "Older volcanic-ash-bearing deposit (inferred)",
    "SYN-SURFACE-COVER": "Surface and colluvial cover (inferred)",
    "SYN-SILTSTONE": "Siltstone-dominant interval (inferred)",
    "SYN-SANDSTONE": "Sandstone-dominant interval (inferred)",
    "SYN-SAND-MUD-ALT": "Alternating sandstone and mudstone (inferred)",
    "SYN-MUDSTONE": "Mudstone-dominant interval (inferred)",
    "SYN-CONGLOMERATE": "Conglomerate and sandstone interval (inferred)",
    "SYN-TUFFACEOUS": "Tuffaceous sedimentary interval (inferred)",
    "SYN-OLDER-SEDIMENTARY": "Older sedimentary rocks; display base (inferred)",
    "SYN-PALEOSOL": "Paleosol and weathered horizon (inferred)",
    "SYN-CALCAREOUS": "Calcareous sandstone and mudstone (inferred)",
    "SYN-VOLCANIC-CONGLOMERATE": "Volcaniclastic conglomerate (inferred)",
    "SYN-OLD-SANDSTONE": "Older sandstone-dominant interval (inferred)",
    "SYN-OLD-MUDSTONE": "Older mudstone-dominant interval (inferred)",
    "SYN-OLD-TUFFACEOUS": "Older tuffaceous sedimentary interval (inferred)",
    "SYN-OLD-CONGLOMERATE": "Older conglomeratic interval (inferred)",
    "SYN-TEPHRA-SCORIA": "Fallout tephra and scoria (inferred)",
    "SYN-TUFF": "Tuffaceous interval (inferred)",
    "SYN-VOLCANIC-EDIFICE": "Lava and pyroclastic edifice complex (inferred)",
    "SYN-PYROCLASTIC": "Pyroclastic rock and tuff breccia (inferred)",
    "SYN-LAVA-BRECCIA": "Lava and volcanic breccia interval (inferred)",
    "SYN-INTERMEDIATE-LAVA": "Intermediate-composition lava (inferred)",
    "SYN-ALTERED-VOLCANIC": "Altered volcanic rocks (inferred)",
    "SYN-OLDER-VOLCANIC": "Older volcanic rocks; display base (inferred)",
    "SYN-OLD-LAVA-SEQUENCE": "Older lava-flow sequence (inferred)",
    "SYN-OLD-TUFF-BRECCIA": "Older tuff-breccia sequence (inferred)",
    "SYN-OLD-VOLCANICLASTIC": "Older volcaniclastic interval (inferred)",
    "SYN-HYDROTHERMAL-ZONE": "Hydrothermally altered volcanic zone (inferred)",
    "SYN-OLD-IGNIMBRITE": "Older ignimbrite and welded-tuff interval (inferred)",
    "SYN-PALEOSOL-TEPHRA": "Paleosol and reworked tephra (inferred)",
    "SYN-WELDED-TUFF": "Welded pyroclastic-flow deposit (inferred)",
    "SYN-LAHAR": "Lahar and debris-flow deposit (inferred)",
    "SYN-WEATHERED-LAVA": "Weathered lava-top zone (inferred)",
    "SYN-MUDSTONE-MATRIX": "Mudstone matrix (inferred)",
    "SYN-WEATHERED-ACCRETIONARY": "Weathered accretionary-complex zone (inferred)",
    "SYN-SANDSTONE-BLOCK": "Sandstone-dominant block or slice (inferred)",
    "SYN-CHERT-BLOCK": "Chert-rich block or slice (inferred)",
    "SYN-SILICEOUS-MUD": "Siliceous mudstone block or slice (inferred)",
    "SYN-GREENSTONE": "Greenstone-rich block or slice (inferred)",
    "SYN-MIXED-ROCK": "Mixed-rock interval (inferred)",
    "SYN-OLDER-COMPLEX": "Older accretionary complex; display base (inferred)",
    "SYN-RESIDUAL-SOIL": "Residual soil and highly weathered zone (inferred)",
    "SYN-MASADO": "Grus-like weathered parent rock (inferred)",
    "SYN-HIGH-WEATHERED": "Highly weathered plutonic rock (inferred)",
    "SYN-WEATHERED-PLUTON": "Weathered plutonic rock (inferred)",
    "SYN-FRACTURED-PLUTON": "Fractured plutonic rock (inferred)",
    "SYN-FRESH-PLUTON": "Relatively fresh plutonic rock (inferred)",
    "SYN-DEEP-PLUTON": "Plutonic rock; display base (inferred)",
    "SYN-WEATHERED-METAMORPHIC": "Weathered metamorphic-rock zone (inferred)",
    "SYN-PELMET": "Pelitic metamorphic-rock dominant zone (inferred)",
    "SYN-PSAMMET": "Psammitic metamorphic-rock dominant zone (inferred)",
    "SYN-SCHISTOSE-MIXED": "Schistose mixed metamorphic zone (inferred)",
    "SYN-QUARTZOSE-METAMORPHIC": "Quartz-rich metamorphic zone (inferred)",
    "SYN-MIXED-METAMORPHIC": "Mixed metamorphic-rock zone (inferred)",
    "SYN-DEEP-METAMORPHIC": "Metamorphic rocks; display base (inferred)",
}

DOMAIN_FACIES = {
    "UnconsolidatedSedimentTerrain": [
        ("ADV2-SURFACE-SOIL", "表土・人工改変の可能性を含む表層（推定）", 1.2, "#9b805e", "SurfaceCover"),
        ("ADV2-ORGANIC-FINE", "有機質を含む粘土・シルト（推定）", 2.8, "#7f8b7a", "FineSediment"),
        ("ADV2-CLAY", "粘土質堆積物（推定）", 4.2, "#98a6a3", "FineSediment"),
        ("ADV2-SILT", "シルト質堆積物（推定）", 5.0, "#aaa99d", "FineSediment"),
        ("ADV2-SAND", "砂質堆積物（推定）", 7.0, "#d6bd76", "CoarseSediment"),
        ("ADV2-GRAVELLY-SAND", "れきまじり砂（推定）", 7.5, "#bf9b69", "CoarseSediment"),
        ("ADV2-GRAVEL", "砂れき（推定）", 9.0, "#aa8564", "CoarseSediment"),
        ("ADV2-PEAT", "高有機質土（泥炭）（推定）", 2.2, "#665b45", "FineSediment"),
        ("ADV2-OLD-CLAY", "更新統の粘土質堆積物（推定）", 8.0, "#7d8988", "FineSediment"),
        ("ADV2-OLD-SAND", "更新統の砂質堆積物（推定）", 18.0, "#b8a477", "CoarseSediment"),
        ("ADV2-OLD-GRAVEL", "更新統の砂れき質堆積物（推定）", 22.0, "#92765f", "CoarseSediment"),
        ("ADV2-OLD-SILT-CLAY", "更新統のシルト・粘土質堆積物（推定）", 18.0, "#747f7d", "FineSediment"),
        ("ADV2-OLD-VOLCANIC-ASH", "更新統の火山灰質堆積物（推定）", 14.0, "#948a7d", "FineSediment"),
        ("ADV2-OLDER-SEDIMENT", "更新統または下位の堆積物・表示基底（推定）", 36.0, "#666866", "DisplayBase")],
    "SedimentaryRockTerrain": [
        ("SYN-SURFACE-COVER", "表土・崩積性被覆（推定）", 2.0, "#a58b68", "SurfaceCover"),
        ("SYN-SILTSTONE", "シルト岩優勢層（推定）", 9.0, "#a9aaa0", "FineClastic"),
        ("SYN-SANDSTONE", "砂岩優勢層（推定）", 14.0, "#d2b46d", "CoarseClastic"),
        ("SYN-SAND-MUD-ALT", "砂岩・泥岩互層（推定）", 13.0, "#b49a78", "AlternatingClastic"),
        ("SYN-MUDSTONE", "泥岩優勢層（推定）", 16.0, "#84928e", "FineClastic"),
        ("SYN-CONGLOMERATE", "礫岩・砂岩互層（推定）", 18.0, "#a17c61", "CoarseClastic"),
        ("SYN-TUFFACEOUS", "凝灰質堆積岩層（推定）", 12.0, "#988d80", "VolcaniclasticMarker"),
        ("SYN-PALEOSOL", "古土壌・風化層準（推定）", 3.5, "#8b6754", "VolcaniclasticMarker"),
        ("SYN-CALCAREOUS", "石灰質砂岩・泥岩層（推定）", 10.0, "#b8b29c", "FineClastic"),
        ("SYN-VOLCANIC-CONGLOMERATE", "火山砕屑性礫岩層（推定）", 12.0, "#9b765f", "CoarseClastic"),
        ("SYN-OLD-SANDSTONE", "下位砂岩優勢層（推定）", 22.0, "#aa936d", "CoarseClastic"),
        ("SYN-OLD-MUDSTONE", "下位泥岩優勢層（推定）", 24.0, "#707b79", "FineClastic"),
        ("SYN-OLD-TUFFACEOUS", "下位凝灰質堆積岩層（推定）", 18.0, "#877d74", "VolcaniclasticMarker"),
        ("SYN-OLD-CONGLOMERATE", "下位礫岩層（推定）", 22.0, "#806654", "CoarseClastic"),
        ("SYN-OLDER-SEDIMENTARY", "下位堆積岩類・表示基底（推定）", 38.0, "#676a68", "DisplayBase")],
    "VolcanicTerrain": [
        ("SYN-SURFACE-COVER", "表土・薄層火山灰被覆（推定）", 2.0, "#8f7659", "SurfaceCover"),
        ("SYN-TEPHRA-SCORIA", "降下火砕物・スコリア質層（推定）", 5.0, "#b58a62", "Tephra"),
        ("SYN-PALEOSOL-TEPHRA", "古土壌・再堆積火山灰層（推定）", 3.0, "#85634f", "Tephra"),
        ("SYN-VOLCANIC-EDIFICE", "溶岩・火砕岩複合岩体（推定）", 20.0, "#8d766e", "EdificeRockMass"),
        ("SYN-TUFF", "凝灰岩質層（推定）", 8.0, "#aa9582", "Pyroclastic"),
        ("SYN-WELDED-TUFF", "溶結火砕流堆積物（推定）", 11.0, "#9a7f72", "Pyroclastic"),
        ("SYN-LAHAR", "ラハール・土石流堆積物（推定）", 7.0, "#796f62", "Pyroclastic"),
        ("SYN-LAVA-BRECCIA", "溶岩・火山角礫岩互層（推定）", 14.0, "#806c75", "LavaBreccia"),
        ("SYN-WEATHERED-LAVA", "風化溶岩上面帯（推定）", 4.5, "#74665f", "AlteredVolcanic"),
        ("SYN-INTERMEDIATE-LAVA", "中性火山岩質溶岩（推定）", 18.0, "#625f68", "Lava"),
        ("SYN-ALTERED-VOLCANIC", "変質火山岩類（推定）", 14.0, "#777476", "AlteredVolcanic"),
        ("SYN-OLD-LAVA-SEQUENCE", "下位溶岩流累重層（推定）", 32.0, "#5b5961", "Lava"),
        ("SYN-OLD-TUFF-BRECCIA", "下位凝灰角礫岩層（推定）", 28.0, "#70666a", "Pyroclastic"),
        ("SYN-OLD-VOLCANICLASTIC", "下位火山砕屑岩層（推定）", 24.0, "#6d6259", "Pyroclastic"),
        ("SYN-HYDROTHERMAL-ZONE", "熱水変質火山岩帯（推定）", 26.0, "#696d68", "AlteredVolcanic"),
        ("SYN-OLD-IGNIMBRITE", "下位溶結凝灰岩層（推定）", 30.0, "#625952", "Pyroclastic"),
        ("SYN-OLDER-VOLCANIC", "下位火山岩類・表示基底（推定）", 30.0, "#514e52", "DisplayBase")],
    "AccretionaryComplex": [
        ("SYN-SURFACE-COVER", "表土・崩積性被覆（推定）", 2.0, "#9b8264", "SurfaceCover"),
        ("SYN-WEATHERED-ACCRETIONARY", "風化付加体岩盤（母岩状態・推定）", 6.0, "#929087", "WeatheringState"),
        ("SYN-MUDSTONE-MATRIX", "泥質岩基質（推定）", 11.0, "#777f7f", "Matrix"),
        ("SYN-SANDSTONE-BLOCK", "砂岩優勢岩体（推定）", 13.0, "#b89d68", "BlockOrSlice"),
        ("SYN-CHERT-BLOCK", "チャート質岩体（推定）", 11.0, "#8e7770", "BlockOrSlice"),
        ("SYN-GREENSTONE", "緑色岩質岩体（推定）", 12.0, "#6f8275", "BlockOrSlice"),
        ("SYN-MIXED-ROCK", "混在岩相（推定）", 18.0, "#686d70", "MixedComplex"),
        ("SYN-OLDER-COMPLEX", "下位付加体・表示基底（推定）", 75.0, "#51565a", "DisplayBase")],
    "PlutonicTerrain": [
        ("SYN-SURFACE-COVER", "表土・崩積性被覆（推定）", 1.8, "#9c8262", "SurfaceCover"),
        ("SYN-RESIDUAL-SOIL", "残積土・強風化帯（推定）", 2.5, "#c4aa7f", "WeatheringState"),
        ("SYN-MASADO", "まさ状風化帯（母岩状態・推定）", 4.0, "#d0b98a", "WeatheringState"),
        ("SYN-HIGH-WEATHERED", "強風化深成岩体（推定）", 7.0, "#c0ad96", "WeatheringState"),
        ("SYN-WEATHERED-PLUTON", "風化深成岩体（推定）", 10.0, "#b6a48e", "WeatheringState"),
        ("SYN-FRACTURED-PLUTON", "割れ目を伴う深成岩体（推定）", 16.0, "#9a8e82", "FractureState"),
        ("SYN-FRESH-PLUTON", "比較的新鮮な深成岩体（推定）", 28.0, "#817b76", "FreshRock"),
        ("SYN-DEEP-PLUTON", "深成岩体・表示基底（推定）", 75.0, "#686563", "DisplayBase")],
    "MetamorphicBelt": [
        ("SYN-SURFACE-COVER", "表土・崩積性被覆（推定）", 2.0, "#9b8264", "SurfaceCover"),
        ("SYN-WEATHERED-METAMORPHIC", "風化変成岩帯（推定）", 7.0, "#958b80", "WeatheringState"),
        ("SYN-PELMET", "泥質変成岩優勢帯（推定）", 13.0, "#77767b", "Metasedimentary"),
        ("SYN-PSAMMET", "砂質変成岩優勢帯（推定）", 15.0, "#9b8d78", "Metasedimentary"),
        ("SYN-SCHISTOSE-MIXED", "片理を伴う変成岩帯（推定）", 15.0, "#777982", "FoliatedMixed"),
        ("SYN-QUARTZOSE-METAMORPHIC", "珪質変成岩質帯（推定）", 12.0, "#8b8985", "Metasedimentary"),
        ("SYN-MIXED-METAMORPHIC", "混合変成岩帯（推定）", 18.0, "#686a72", "FoliatedMixed"),
        ("SYN-DEEP-METAMORPHIC", "変成岩類・表示基底（推定）", 75.0, "#52545b", "DisplayBase")],
}


def select_evidence_bounded_lithologies(profile: dict, domain: str, plan: dict) -> dict:
    result = copy.deepcopy(profile)
    rows = DOMAIN_FACIES.get(domain)
    if not rows:
        result["lithologySelection"] = {"policyId": POLICY_ID, "passed": True,
            "status": "ExistingProfileRetained", "selectedCount": len(result.get("substrateFacies", []))}
        return result
    major_evidence = resolve_major_lithology_evidence(plan, domain)
    rows = specialize_domain_rows(rows, domain, major_evidence)
    regional_data = regional_dataset_for_plan(plan)
    replacements = composite_specializations(domain, major_evidence)
    bedrock = None
    excluded = []
    if domain == "UnconsolidatedSedimentTerrain":
        if not has_ash_evidence(plan):
            rows = [row for row in rows if row[0] != "ADV2-OLD-VOLCANIC-ASH"]
            excluded.append({"unitId":"ADV2-OLD-VOLCANIC-ASH", "reason":"NoRegionalAshEvidence"})
        bedrock = resolve_regional_bedrock(plan)
        if bedrock["selected"]:
            rock = bedrock["selected"]
            # Replace the generic sedimentary display base with a source-linked
            # substrate, not an extra granite bed in a sedimentary succession.
            rows[-1] = ("ADV2-REGIONAL-" + rock["key"].upper(),
                        rock["ja"] + "（地域推定・基盤岩）", rows[-1][2], "#c58d89", "DisplayBase")
    if any("層群" in row[1] or "累層" in row[1] or "Formation" in row[1] for row in rows):
        raise ValueError("invented formal stratigraphic names are prohibited")
    architecture = plan_facies_architecture(domain, rows)
    if not architecture["passed"]:
        raise ValueError("facies architecture rejected: " + ",".join(architecture["errors"]))
    result["substrateFacies"] = [list(row[:4]) for row in architecture["geometricRows"]]
    labels = dict(result.get("englishUnitLabels", {}))
    labels.update({row[0]: ENGLISH_LABELS.get(row[0], row[0]) for row in rows})
    labels.update(specialized_english_labels(domain, major_evidence))
    labels.update({key:value["en"] for key,value in replacements.items()})
    if bedrock and bedrock["selected"]:
        labels[rows[-1][0]] = bedrock["selected"]["en"] + " substrate (regionally inferred)"
    result["englishUnitLabels"] = labels
    source_labels = {row[0]: row[1] for row in profile.get("substrateFacies", []) if len(row) > 1}
    result["faciesMetadata"] = [{"unitId":row[0], "materialRole":row[4],
        "declaredMeanThicknessM":float(row[2]),
        "basisType":"SyntheticAssumption", "sourceIds":["GSJ-SEAMLESS-V2-LEGEND","CGI-GEOSCIML-LITHOLOGY"],
        "portrayalRole":("GeometricBody" if row in architecture["geometricRows"] else "UnlocatedCompositionPart"),
        "formationNameInvented":False, "localObservationClaim":False,
        "terminology":terminology_record(row[0], source_labels.get(row[0], row[1]), row[1],
                                           labels.get(row[0], row[0]))} for row in rows]
    result["terminologyCurrencyAudit"] = audit_publication_terminology(result["faciesMetadata"])
    if not result["terminologyCurrencyAudit"]["passed"]:
        raise ValueError("current geological terminology gate rejected: " +
                         ";".join(result["terminologyCurrencyAudit"]["errors"]))
    result["faciesArchitecture"] = {key:value for key,value in architecture.items()
        if key not in {"geometricRows", "compositionRows"}}
    result["faciesArchitecture"]["compositionParts"] = [{"unitId":row[0], "materialRole":row[4],
        "basisType":"SyntheticAssumption", "geometryAuthorized":False} for row in architecture["compositionRows"]]
    result["majorLithologyEvidence"] = major_evidence
    result["regionalLithologySelection"] = selection_accounting(
        regional_data, domain, rows, replacements, bedrock,
        geometric_ids=[r[0] for r in architecture["geometricRows"]])
    result["regionalLithologyInputId"] = regional_data["datasetId"]
    for metadata in result["faciesMetadata"]:
        spec = replacements.get(metadata["unitId"])
        if spec:
            metadata["regionalMemberKeys"] = spec["memberKeys"]
            metadata["regionalRepresentation"] = spec["representation"]
            metadata["regionalSourceRecordIds"] = sorted({rid for c in regional_data["candidates"]
                if c["key"] in spec["memberKeys"] for rid in c["recordIds"]})
    if bedrock:
        result["regionalBedrockEvidence"] = bedrock
        if bedrock["selected"]:
            result["faciesMetadata"][-1].update(
                sourceIds=bedrock["sourceIds"], regionalEvidence=bedrock,
                parentLithologyKey=bedrock["selected"]["key"],
                contactClass="InferredCoverBedrockContact")
    result["burialConditioning"] = burial_conditioning_metadata(
        architecture["geometricRows"], domain)
    result["effectiveLithologyDiversityAudit"] = audit_effective_lithology_diversity(
        domain, major_evidence, architecture["geometricRows"])
    result["lithologySelection"] = {"policyId":POLICY_ID, "passed":True,
        "status":"CompatibleBroadPriorSubset", "domain":domain,
        "selectedCount":len(architecture["geometricRows"]), "candidateLithologyCount":len(rows),
        "compositionPartCount":len(architecture["compositionRows"]), "observedCount":0, "literatureCount":0,
        "syntheticAssumptionCount":len(rows),
        "mappedSurfaceEvidenceUsedAsVerticalSequence":False,
        "specificMappedLithologyPrior":major_evidence.get("selectedLabelJa"),
        "rockTypeSelectedFromDepth":False,
        "hardnessDerivedFromDepth":False,
        "excludedUnsupportedCandidates":excluded,
        "regionalBedrockSelectionStatus":bedrock["status"] if bedrock else "NotApplicable",
        "sourceIds":["GSJ-SEAMLESS-V2-LEGEND","GSJ-ZFK-LEGEND","CGI-GEOSCIML-LITHOLOGY"],
        "limitations":["Broad candidates are not a local vertical sequence",
                       "Formal formation names require route-applicable evidence"]}
    return result
