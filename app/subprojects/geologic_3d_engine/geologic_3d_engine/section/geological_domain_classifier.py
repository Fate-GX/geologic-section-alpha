"""Classify a route-scale geological domain from plan evidence.

Mapped geological lithology is the primary evidence. Terrain is reported as a
separate landform context and is never allowed to choose the geological domain.
"""
from __future__ import annotations

import math
import re

DOMAIN_RULES = {
    "VolcanicTerrain": ("火山岩", "溶岩", "火砕岩", "凝灰岩", "玄武岩", "安山岩",
                        "デイサイト", "流紋岩", "volcan", "lava", "pyroclast", "tuff"),
    "PlutonicTerrain": ("深成岩", "花崗岩", "閃緑岩", "斑れい岩", "granite", "granodiorite",
                        "diorite", "gabbro", "plutonic"),
    "MetamorphicBelt": ("変成岩", "結晶片岩", "片麻岩", "千枚岩", "ホルンフェルス",
                        "metamorph", "schist", "gneiss", "phyllite", "hornfels"),
    "AccretionaryComplex": ("付加体", "メランジュ", "チャート", "混在岩", "accretionary",
                            "mélange", "melange", "chert"),
    "SedimentaryRockTerrain": ("堆積岩", "砕屑岩", "海成層", "砂岩", "泥岩", "頁岩", "礫岩", "石灰岩",
                               "clastic rock", "marine sedimentary", "sandstone", "mudstone", "shale",
                               "conglomerate", "limestone"),
    "UnconsolidatedSedimentTerrain": ("未固結", "沖積", "谷底平野", "山間盆地", "河川", "海岸平野",
                                      "湖沼", "湿原", "湿地堆積物", "砂・泥", "砂・礫", "粘土", "シルト",
                                      "unconsolidated", "alluv", "valley floor", "coastal plain",
                                      "sand and mud", "gravel"),
    "ArtificiallyModifiedTerrain": ("盛土", "埋立", "干拓", "人工改変", "reclaimed", "artificial fill")
}


def _domain_for_legend(legend):
    text=" ".join(str(legend.get(key,"")) for key in
                  ("title","lithology_ja","lithology_en")).casefold()
    matches=[]
    for domain,terms in DOMAIN_RULES.items():
        if any(term.casefold() in text for term in terms):matches.append(domain)
    # Specific process/rock families take precedence over generic sediment text.
    precedence=("ArtificiallyModifiedTerrain","AccretionaryComplex","MetamorphicBelt",
                "PlutonicTerrain","VolcanicTerrain","UnconsolidatedSedimentTerrain",
                "SedimentaryRockTerrain")
    return next((domain for domain in precedence if domain in matches),"Unresolved")


def _sample_weights(samples,total_length):
    stations=[float(row["stationM"]) for row in samples]
    weights=[]
    for index,station in enumerate(stations):
        left=0.0 if index==0 else (stations[index-1]+station)/2
        right=total_length if index==len(stations)-1 else (station+stations[index+1])/2
        weights.append(max(0.0,right-left))
    return weights


def classify_plan_geological_domain(plan, *, dominance_threshold=.65):
    if not isinstance(plan,dict) or plan.get("schemaVersion")!="PlanEvidenceBundle-1.0":
        raise ValueError("PlanEvidenceBundle-1.0 is required")
    terrain=plan.get("terrainProfile");samples=plan.get("surfaceGeology",{}).get("samples")
    if not isinstance(terrain,list) or len(terrain)<2 or not isinstance(samples,list) or not samples:
        raise ValueError("terrain and mapped surface geology are required")
    total=float(terrain[-1]["stationM"])
    if not math.isfinite(total) or total<=0:raise ValueError("positive route length required")
    ordered=sorted(samples,key=lambda row:float(row["stationM"]))
    if any(float(row["stationM"])<0 or float(row["stationM"])>total for row in ordered):
        raise ValueError("geology sample outside route")
    weights=_sample_weights(ordered,total);scores={};evidence=[]
    for row,weight in zip(ordered,weights):
        legend=row.get("legend");domain="Unresolved" if not isinstance(legend,dict) else _domain_for_legend(legend)
        scores[domain]=scores.get(domain,0.0)+weight
        evidence.append({"stationM":float(row["stationM"]),"weightM":weight,
                         "symbol":None if not legend else legend.get("symbol"),
                         "sourceLithology":None if not legend else legend.get("lithology_ja"),
                         "classifiedDomain":domain})
    fractions={key:value/total for key,value in scores.items()};ranked=sorted(fractions,key=lambda key:(-fractions[key],key))
    dominant=ranked[0]
    geological_domain=(dominant if dominant!="Unresolved" and fractions[dominant]>=dominance_threshold
                       else "MixedGeologicalDomain" if len([v for k,v in fractions.items() if k!="Unresolved" and v>0])>1
                       else "Unresolved")
    elevations=[float(row["elevationM"]) for row in terrain]
    relief=max(elevations)-min(elevations)
    mean_grade=relief/total
    landform=("MountainousRelief" if relief>=100 or mean_grade>=.12 else
              "HillyRelief" if relief>=30 or mean_grade>=.04 else "LowRelief")
    source=plan["surfaceGeology"]
    return {"schemaVersion":"PlanGeologicalDomainClassification-1.0",
      "geologicalDomain":geological_domain,"dominantMappedDomain":dominant,
      "domainFractionsByRouteLength":fractions,"dominanceThreshold":float(dominance_threshold),
      "landformContext":landform,"terrainReliefM":relief,"routeLengthM":total,
      "terrainDeterminedGeologicalDomain":False,"primaryEvidence":"MappedSurfaceGeology",
      "sourceId":source.get("sourceId"),"sourceEdition":source.get("sourceEdition"),
      "sampleEvidence":evidence,"subsurfaceMeaning":"PriorSelectorOnly_NotSubsurfaceObservation",
      "passed":geological_domain!="Unresolved"}
