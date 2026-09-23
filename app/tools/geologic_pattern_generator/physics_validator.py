"""Deterministic property sweep for geological pattern invariants."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from engine import ProcessRule, load_catalog, thickness, validate_parameters


FINITE = {"finite_asymmetric_lobe", "channel_lens", "source_directed_wedge"}


def _valid_parameters(rule: ProcessRule, rng: random.Random):
    p = {name: lo + (hi - lo) * rng.random()
         for name, (lo, hi) in rule.parameter_ranges.items()}
    if "start" in p and "end" in p:
        start = rng.uniform(0.02, 0.55)
        end = rng.uniform(max(start + 0.12, 0.6), 0.98)
        p["start"], p["end"] = start, end
    if "peak" in p:
        p["peak"] = rng.uniform(p["start"] + .2 * (p["end"]-p["start"]),
                                p["end"] - .2 * (p["end"]-p["start"]))
    if rule.geometry_family == "source_directed_wedge":
        p["source"] = rng.uniform(p["start"], p["end"])
    return p


def _contiguous(active):
    indices = [i for i, value in enumerate(active) if value]
    return not indices or indices == list(range(indices[0], indices[-1] + 1))


def validate_rule(rule: ProcessRule, cases=200, samples=1001, seed=260826):
    if not rule.stack_supported:
        return {"processId": rule.process_id, "status": "CorrectlyDelegated",
                "caseCount": 0, "failures": []}
    rng = random.Random(seed + sum(map(ord, rule.process_id)))
    failures = []
    u_values = [i / (samples - 1) for i in range(samples)]
    for case_index in range(cases):
        p = _valid_parameters(rule, rng)
        evidence = list(rule.required_evidence)
        parameter_errors = validate_parameters(rule, p, evidence)
        if parameter_errors:
            failures.append({"case": case_index, "code": "GeneratedValidCaseRejected",
                             "details": parameter_errors})
            continue
        values = [thickness(rule, u, p) for u in u_values]
        if any(not math.isfinite(v) or v < 0 for v in values):
            failures.append({"case": case_index, "code": "NonFiniteOrNegativeThickness"})
            continue
        if rule.geometry_family in FINITE:
            active = [v > 1e-8 for v in values]
            if values[0] > 1e-8 or values[-1] > 1e-8:
                failures.append({"case": case_index, "code": "FiniteBodyTouchesSectionEnd"})
            if not _contiguous(active):
                failures.append({"case": case_index, "code": "FragmentedFiniteBody"})
            maximum = p["maximum"]
            if max(values) > maximum * 1.0001:
                failures.append({"case": case_index, "code": "MaximumParameterExceeded",
                                 "actual": max(values), "specified": maximum})
            if thickness(rule, p["start"], p) > 1e-10 or thickness(rule, p["end"], p) > 1e-10:
                failures.append({"case": case_index, "code": "EndpointDoesNotTaper"})
        if rule.geometry_family == "source_attenuating_drape":
            left = [v for u, v in zip(u_values, values) if u <= p["source"]]
            right = [v for u, v in zip(u_values, values) if u >= p["source"]]
            if any(left[i] > left[i+1] + 1e-9 for i in range(len(left)-1)):
                failures.append({"case": case_index, "code": "UpwindNotMonotonicTowardSource"})
            if any(right[i] < right[i+1] - 1e-9 for i in range(len(right)-1)):
                failures.append({"case": case_index, "code": "DownwindNotMonotonicFromSource"})
        # A larger amplitude/maximum must never make the body thinner.
        scale_key = "maximum" if "maximum" in p else "amplitude" if "amplitude" in p else None
        if scale_key:
            p2 = dict(p);p2[scale_key] *= 1.01
            values2 = [thickness(rule, u, p2) for u in u_values]
            if any(b + 1e-9 < a for a, b in zip(values, values2)):
                failures.append({"case": case_index, "code": "NonMonotonicScaleResponse"})
    return {"processId": rule.process_id, "status": "Passed" if not failures else "Failed",
            "caseCount": cases, "failures": failures}


def run(catalog_path: Path, output_path: Path | None = None, cases=200):
    catalog = load_catalog(catalog_path)
    results = [validate_rule(rule, cases=cases) for rule in catalog.values()]
    report = {"schemaVersion": "1.0.0", "casesPerSupportedProcess": cases,
              "processCount": len(results),
              "supportedProcessCount": sum(r["caseCount"] > 0 for r in results),
              "totalGeneratedCases": sum(r["caseCount"] for r in results),
              "failureCount": sum(len(r["failures"]) for r in results),
              "passed": all(r["status"] in {"Passed", "CorrectlyDelegated"} for r in results),
              "results": results}
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    report = run(here / "process_catalog.json",
                 here.parents[1] / "outputs/geologic_pattern_physics_validation.json")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 2)
