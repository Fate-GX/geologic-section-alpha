"""Scope-preserving calibration checks against observed geological datasets."""

from __future__ import annotations

import json
from pathlib import Path


def load_observed_calibration(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("datasetId") or not data.get("scope") or not data.get("sourceIds"):
        raise ValueError("calibration dataset lacks identity, scope or provenance")
    if not data.get("observations"):
        raise ValueError("calibration dataset has no observations")
    return data


def observation_by_id(dataset: dict, observation_id: str) -> dict:
    for record in dataset["observations"]:
        if record["observationId"] == observation_id:
            return record
    raise KeyError(observation_id)


def compare_buried_valley_candidate(dataset: dict, *, width_m: float, depth_m: float,
                                    observation_id: str) -> dict:
    """Compare with one named observation; never manufacture a pooled global range."""
    width, depth = float(width_m), float(depth_m)
    if width <= 0 or depth <= 0:
        raise ValueError("candidate width and depth must be positive")
    observed = observation_by_id(dataset, observation_id)
    result = {
        "datasetId": dataset["datasetId"], "scope": dataset["scope"],
        "observationId": observation_id, "candidateWidth_m": width,
        "candidateDepth_m": depth, "candidateAspectRatio": width / depth,
        "evidenceClass": "ObservedComparison", "passed": None, "checks": []
    }
    observed_width = observed.get("upperWidth_m", {})
    observed_depth = observed.get("depth_m", {})
    if "value" in observed_width:
        result["checks"].append({"metric": "upperWidth_m", "observed": observed_width,
                                  "candidate": width, "difference": width - observed_width["value"]})
    if "value" in observed_depth:
        result["checks"].append({"metric": "depth_m", "observed": observed_depth,
                                  "candidate": depth, "difference": depth - observed_depth["value"]})
    if "derivedAspectRatio_width_depth" in observed:
        ratio = observed["derivedAspectRatio_width_depth"]
        result["checks"].append({"metric": "widthDepthRatio", "observed": ratio,
                                  "candidate": width / depth, "difference": width / depth - ratio})
    result["passed"] = False
    result["decision"] = "RequiresExplicitToleranceFromStudyDesign"
    result["reason"] = "Approximate published values do not authorize an implicit acceptance tolerance."
    return result


def make_calibration_report(dataset: dict, comparisons: list[dict], *,
                            tolerance_policy_id: str | None = None) -> dict:
    return {
        "datasetId": dataset["datasetId"], "applicabilityScope": dataset["scope"],
        "independentObservedDatasetId": dataset["datasetId"],
        "comparisonCount": len(comparisons), "tolerancePolicyId": tolerance_policy_id,
        "passed": bool(comparisons and tolerance_policy_id and all(x.get("passed") for x in comparisons)),
        "state": "Calibrated" if tolerance_policy_id and all(x.get("passed") for x in comparisons)
                 else "ObservedButNotYetThresholdCalibrated"
    }
