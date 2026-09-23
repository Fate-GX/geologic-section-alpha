"""Extract reusable statistics from forward-model section outputs.

Simulation output is hypothesis data, not field truth.  The returned statistics
remain `SimulationDerived` until compared with an authoritative observation set.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Mapping, Sequence


def _runs(active: Sequence[bool]) -> list[int]:
    lengths, current = [], 0
    for value in active:
        if value:
            current += 1
        elif current:
            lengths.append(current)
            current = 0
    if current:
        lengths.append(current)
    return lengths


def _lag1(values: Sequence[float]) -> float | None:
    if len(values) < 3 or len(set(values)) < 2:
        return None
    try:
        return statistics.correlation(values[:-1], values[1:])
    except statistics.StatisticsError:
        return None


def extract_section_patterns(model: Mapping, *, tool_id: str, scenario_id: str,
                             parameter_manifest_id: str) -> dict:
    """Extract dimensionless/coordinate-aware section metrics from canonical output."""
    x = [float(v) for v in model["x"]]
    if len(x) < 2 or any(b <= a for a, b in zip(x, x[1:])):
        raise ValueError("x must be strictly increasing")
    spacing = statistics.median([b - a for a, b in zip(x, x[1:])])
    units, vertical_pairs = [], Counter()
    previous = None
    for unit in model["units"]:
        thickness = [max(0.0, float(t) - float(b))
                     for t, b in zip(unit["top"], unit["bottom"])]
        active = [value > 1e-9 for value in thickness]
        positive = [value for value in thickness if value > 1e-9]
        runs = _runs(active)
        mean = statistics.fmean(positive) if positive else 0.0
        std = statistics.pstdev(positive) if len(positive) > 1 else 0.0
        process_id = unit.get("processId", "Unspecified")
        lithology = unit.get("lithology", process_id)
        if previous is not None:
            vertical_pairs[(previous, lithology)] += 1
        previous = lithology
        units.append({
            "unitId": unit["unitId"], "processId": process_id,
            "lithology": lithology, "meanPositiveThickness": mean,
            "thicknessCoefficientOfVariation": std / mean if mean else None,
            "thicknessLag1Correlation": _lag1(thickness),
            "activeFraction": sum(active) / len(active),
            "connectedBodyCount": len(runs),
            "maximumConnectedLength": max(runs, default=0) * spacing,
            "pinchoutBoundaryCount": sum(a != b for a, b in zip(active, active[1:])),
        })
    return {
        "schemaVersion": "1.0.0", "evidenceClass": "SimulationDerived",
        "toolId": tool_id, "scenarioId": scenario_id,
        "parameterManifestId": parameter_manifest_id,
        "sectionSpacing": spacing, "unitMetrics": units,
        "verticalTransitionCounts": [
            {"from": a, "to": b, "count": count}
            for (a, b), count in sorted(vertical_pairs.items())
        ],
        "adoptionState": "RequiresObservedCalibration",
        "prohibitedUse": "Do not treat simulator frequency as natural-world probability.",
    }


def evaluate_adoption(simulation_metrics: Mapping, calibration_report: Mapping | None) -> dict:
    """Block promotion unless an explicit independent calibration report passes."""
    passed = bool(calibration_report and calibration_report.get("passed") is True
                  and calibration_report.get("independentObservedDatasetId")
                  and calibration_report.get("applicabilityScope"))
    return {
        "adoptable": passed,
        "state": "CalibratedCandidate" if passed else "SimulationHypothesisOnly",
        "toolId": simulation_metrics.get("toolId"),
        "required": [] if passed else [
            "independentObservedDatasetId", "applicabilityScope", "passed calibration thresholds"
        ],
    }
