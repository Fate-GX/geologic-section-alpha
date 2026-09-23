"""Process-conditioned lithology transitions with leave-one-region-out validation."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Iterable, Mapping


def _validate(records: Iterable[Mapping]) -> list[Mapping]:
    rows = list(records)
    required = {"regionId", "authorityId", "environment", "process", "sequence"}
    for row in rows:
        missing = required - set(row)
        if missing or len(row["sequence"]) < 2:
            raise ValueError(f"invalid transition record; missing={sorted(missing)}")
    return rows


def fit_transition_model(records: Iterable[Mapping], *, alpha: float = 0.5,
                         boundary_mode: bool = True) -> dict:
    """Fit separate first-order matrices by environment/process.

    boundary_mode excludes self-transitions because interval boundaries encode a
    change. Sampled-grid data must set it False to retain persistence.
    """
    rows = _validate(records)
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    groups = defaultdict(list)
    for row in rows:
        groups[(row["environment"], row["process"])].append(row)
    models = []
    for (environment, process), members in sorted(groups.items()):
        classes = sorted({facies for row in members for facies in row["sequence"]})
        counts = Counter()
        for row in members:
            for source, target in zip(row["sequence"], row["sequence"][1:]):
                if boundary_mode and source == target:
                    continue
                counts[(source, target)] += 1
        probabilities = []
        for source in classes:
            targets = [x for x in classes if not boundary_mode or x != source]
            denominator = sum(counts[(source, target)] for target in targets) + alpha * len(targets)
            for target in targets:
                probabilities.append({
                    "from": source, "to": target, "count": counts[(source, target)],
                    "probability": (counts[(source, target)] + alpha) / denominator
                    if denominator else None
                })
        models.append({
            "environment": environment, "process": process, "classes": classes,
            "regions": sorted({row["regionId"] for row in members}),
            "authorities": sorted({row["authorityId"] for row in members}),
            "transitionProbabilities": probabilities,
            "state": "Candidate" if len({r["regionId"] for r in members}) >= 3
                     and len({r["authorityId"] for r in members}) >= 2 else "InsufficientIndependentCoverage"
        })
    return {"schemaVersion": "1.0.0", "alpha": alpha,
            "boundaryMode": boundary_mode, "models": models}


def _lookup(model: Mapping) -> dict:
    return {(x["from"], x["to"]): x["probability"]
            for x in model["transitionProbabilities"]}


def leave_one_region_out(records: Iterable[Mapping], *, alpha: float = 0.5,
                         boundary_mode: bool = True) -> dict:
    rows = _validate(records)
    regions = sorted({row["regionId"] for row in rows})
    results = []
    for held_out in regions:
        train = [row for row in rows if row["regionId"] != held_out]
        test = [row for row in rows if row["regionId"] == held_out]
        fitted = fit_transition_model(train, alpha=alpha, boundary_mode=boundary_mode)
        by_group = {(m["environment"], m["process"]): _lookup(m) for m in fitted["models"]}
        losses, missing = [], []
        for row in test:
            matrix = by_group.get((row["environment"], row["process"]))
            if matrix is None:
                missing.append({"environment": row["environment"], "process": row["process"]})
                continue
            for source, target in zip(row["sequence"], row["sequence"][1:]):
                if boundary_mode and source == target:
                    continue
                probability = matrix.get((source, target))
                if probability is None:
                    missing.append({"from": source, "to": target})
                else:
                    losses.append(-math.log(probability))
        results.append({"heldOutRegion": held_out, "transitionCount": len(losses),
                        "meanNegativeLogLikelihood": sum(losses) / len(losses) if losses else None,
                        "missingSupport": missing, "passedCoverage": bool(losses) and not missing})
    return {"schemaVersion": "1.0.0", "method": "LeaveOneRegionOut",
            "regions": regions, "results": results,
            "passedCoverage": len(regions) >= 3 and all(x["passedCoverage"] for x in results)}


def promotion_gate(model: Mapping, validation: Mapping) -> dict:
    candidate_models = bool(model["models"]) and all(x["state"] == "Candidate" for x in model["models"])
    passed = candidate_models and validation.get("passedCoverage") is True
    return {"promotable": passed,
            "state": "CrossRegionCandidate" if passed else "ResearchOnly",
            "requirements": [] if passed else ["3 independent regions per group",
                                                "2 independent authorities per group",
                                                "complete held-out transition support"]}
