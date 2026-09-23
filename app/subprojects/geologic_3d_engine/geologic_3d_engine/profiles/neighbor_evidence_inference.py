"""Bounded inference from neighbouring geological evidence.

This module never turns neighbouring evidence into an observation at the target.
It selects compatible candidates and emits an explicitly inferred hypothesis.
"""
from __future__ import annotations

import math
from ..evidence.national_evidence_index import query_national_evidence


def infer_from_national_evidence_index(index, target, *, maximum_distance_m=50000.0,
                                       maximum_sources=5):
    query=query_national_evidence(index,target,maximum_distance_m=maximum_distance_m)
    inference_target={"targetId":target["targetId"],
                      "geologicalProvince":target.get("geologicalProvince"),
                      "ageInterval":target.get("ageApplicability"),
                      "environment":target.get("environmentApplicability")}
    result=infer_from_neighboring_evidence(inference_target,query["matches"],
                                           maximum_distance_m=maximum_distance_m,
                                           maximum_sources=maximum_sources)
    result["nationalIndexQuery"]={"matchCount":len(query["matches"]),
                                  "rejectedCount":len(query["rejections"])}
    result["evidenceWeight"]=0.5;result["universalPriorWeight"]=0.5
    return result


def infer_from_neighboring_evidence(target, candidates, *, maximum_distance_m=50000.0,
                                    maximum_sources=5):
    if not isinstance(target, dict) or not target.get("targetId"):
        raise ValueError("targetId is required")
    if not isinstance(maximum_distance_m, (int, float)) or not math.isfinite(maximum_distance_m) or maximum_distance_m <= 0:
        raise ValueError("maximum_distance_m must be positive and finite")
    if not isinstance(maximum_sources, int) or isinstance(maximum_sources, bool) or maximum_sources < 1:
        raise ValueError("maximum_sources must be a positive integer")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")

    accepted = []
    rejected = []
    for row in candidates:
        required = {"sourceId", "distanceM", "lithologies", "geologicalProvince",
                    "ageInterval", "environment", "evidenceStatus"}
        if not isinstance(row, dict) or not required <= set(row):
            rejected.append({"sourceId": row.get("sourceId") if isinstance(row, dict) else None,
                             "reason": "IncompleteNeighborEvidence"})
            continue
        distance = row["distanceM"]
        if not isinstance(distance, (int, float)) or not math.isfinite(distance) or distance < 0:
            rejected.append({"sourceId": row["sourceId"], "reason": "InvalidDistance"})
            continue
        if distance > maximum_distance_m:
            rejected.append({"sourceId": row["sourceId"], "reason": "OutsideSupportDistance"})
            continue
        mismatches = [key for key in ("geologicalProvince", "ageInterval", "environment")
                      if target.get(key) and row[key] != target[key]]
        if mismatches:
            rejected.append({"sourceId": row["sourceId"],
                             "reason": "GeologicalApplicabilityMismatch",
                             "fields": mismatches})
            continue
        if row["evidenceStatus"] not in {"Observed", "Literature", "Mapped"}:
            rejected.append({"sourceId": row["sourceId"], "reason": "UnsupportedEvidenceStatus"})
            continue
        if not isinstance(row["lithologies"], list) or not row["lithologies"]:
            rejected.append({"sourceId": row["sourceId"], "reason": "EmptyLithologyEvidence"})
            continue
        accepted.append(row)

    accepted.sort(key=lambda value: (float(value["distanceM"]), value["sourceId"]))
    selected = accepted[:maximum_sources]
    if not selected:
        return {"passed": False, "basisType": "Unresolved_NoApplicableNeighborEvidence",
                "targetId": target["targetId"], "selectedSources": [],
                "rejectedCandidates": rejected, "realRegionAuthorized": False}

    scores = {}
    source_ids = {}
    for row in selected:
        weight = 1.0 / (1.0 + float(row["distanceM"]) / maximum_distance_m)
        for lithology in row["lithologies"]:
            if not isinstance(lithology, str) or not lithology.strip():
                continue
            scores[lithology] = scores.get(lithology, 0.0) + weight
            source_ids.setdefault(lithology, []).append(row["sourceId"])
    ordered = sorted(scores, key=lambda name: (-scores[name], name))
    if not ordered:
        return {"passed": False, "basisType": "Unresolved_NoUsableLithologyLabels",
                "targetId": target["targetId"], "selectedSources": [],
                "rejectedCandidates": rejected, "realRegionAuthorized": False}
    nearest = float(selected[0]["distanceM"])
    farthest = float(selected[-1]["distanceM"])
    confidence = "Medium" if len(selected) >= 2 and farthest <= maximum_distance_m * 0.5 else "Low"
    disclosure = (f"地下岩相は対象地点の直接観測ではなく、周辺地域の資料{len(selected)}件"
                  f"（距離 {nearest:.0f}–{farthest:.0f} m）から推定")
    return {"passed": True, "basisType": "InferredFromNeighboringRegionalEvidence",
            "targetId": target["targetId"], "inferredLithologies": ordered,
            "lithologySourceIds": source_ids,
            "selectedSources": [{"sourceId": row["sourceId"], "distanceM": float(row["distanceM"]),
                                  "evidenceStatus": row["evidenceStatus"]} for row in selected],
            "rejectedCandidates": rejected, "supportRadiusM": float(maximum_distance_m),
            "confidence": confidence, "drawingDisclosureJa": disclosure,
            "directTargetEvidence": False, "realRegionAuthorized": False}
