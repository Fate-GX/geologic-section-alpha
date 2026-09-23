"""Stress-test process patterns against varied synthetic terrain families."""

from __future__ import annotations

import json
import math
import random
import statistics
from pathlib import Path

from engine import generate, load_catalog


def terrain(seed: int, family: str, n=401):
    rng = random.Random(seed)
    phase = rng.uniform(-math.pi, math.pi)
    skew = rng.uniform(.35, .65)
    rows = []
    for i in range(n):
        u = i / (n - 1)
        if family == "inclined":
            y = 200 + 80*u + 8*math.sin(2*math.pi*u + phase)
        elif family == "valley":
            y = 260 - 95*math.exp(-((u-skew)/.18)**2) + 12*u
        elif family == "ridge":
            y = 190 + 110*math.exp(-((u-skew)/.22)**2) - 18*u
        elif family == "terrace":
            y = 180 + 38*(u > .28) + 42*(u > .68) + 5*math.sin(4*math.pi*u+phase)
        elif family == "volcanic":
            y = 170 + 125*math.exp(-((u-skew)/.28)**2) + 24*math.exp(-((u-.82)/.09)**2)
        elif family == "compound":
            y = 210 + 45*u + 28*math.sin(2*math.pi*u+phase) + 11*math.sin(6*math.pi*u-phase/2)
        elif family == "near_flat":
            y = 200 + 2.5*u + 1.2*math.sin(2*math.pi*u+phase)
        elif family == "escarpment":
            y = 170 + 105/(1+math.exp(-(u-skew)*45)) + 7*math.sin(2*math.pi*u+phase)
        elif family == "multi_valley":
            y = 260 - 62*math.exp(-((u-.27)/.11)**2) - 88*math.exp(-((u-.73)/.16)**2) + 9*u
        elif family == "caldera_like":
            y = 210 + 105*math.exp(-((u-.12)/.09)**2) + 92*math.exp(-((u-.9)/.12)**2) - 34*math.exp(-((u-.53)/.3)**2)
        else:
            raise ValueError(family)
        rows.append({"distance_m": u*2000, "elevation_m": y})
    return rows


def _slopes(values):
    return [b-a for a, b in zip(values, values[1:])]


def _correlation(a, b):
    sa, sb = _slopes(a), _slopes(b)
    try:
        return statistics.correlation(sa, sb)
    except statistics.StatisticsError:
        return 1.0


def _linear_residual_relief(values):
    start, end = values[0], values[-1]
    residuals = [value - (start + (end-start)*i/(len(values)-1))
                 for i, value in enumerate(values)]
    return max(residuals) - min(residuals)


def representative_config():
    return {"profileId": "TERRAIN_ROBUSTNESS_STACK",
            "qualityPolicy": {"antiMonotonyRequired": True, "minimumDeepResidualRelief": 2.0,
                              "maxCopyLikeSlopeCorrelation": .995, "requireFiniteBody": True},
            "units": [
        {"unitId": "tephra", "processId": "fallout_tephra",
         "parameters": {"minimum": 3, "amplitude": 14, "source": .76, "upwind_width": .18, "downwind_width": .34},
         "evidenceTags": ["volcanic_setting", "tephra_evidence"]},
        {"unitId": "lava", "processId": "lava_flow",
         "parameters": {"start": .08, "end": .88, "maximum": 65, "left_power": .7, "right_power": 1.8},
         "evidenceTags": ["volcanic_setting", "lava_evidence"]},
        {"unitId": "channel", "processId": "fluvial_channel_fill",
         "parameters": {"start": .16, "end": .73, "maximum": 34, "peak": .42, "left_width": .12, "right_width": .2},
         "evidenceTags": ["fluvial_environment", "channel_evidence"]},
        {"unitId": "basin_drape", "processId": "marine_or_lacustrine_drape",
         "parameters": {"minimum": 7, "amplitude": 42, "center": .53, "width": .27},
         "evidenceTags": ["basin_environment", "marine_or_lacustrine_evidence"]}
    ]}


def run(catalog_path: Path, output_path: Path | None = None, seeds=200):
    catalog = load_catalog(catalog_path)
    families = ["inclined", "valley", "ridge", "terrace", "volcanic", "compound",
                "near_flat", "escarpment", "multi_valley", "caldera_like"]
    failures, records = [], []
    for family in families:
        for seed in range(seeds):
            result = generate(representative_config(), terrain(seed, family), catalog)
            if not result["passed"]:
                failures.append({"family": family, "seed": seed, "code": "GenerationFailed", "errors": result["errors"]})
                continue
            contacts = [result["units"][0]["top"]] + [u["bottom"] for u in result["units"]]
            correlations = [_correlation(contacts[i], contacts[i+1]) for i in range(len(contacts)-1)]
            deep_surface_corr = abs(_correlation(contacts[0], contacts[-1]))
            deep_residual_relief = _linear_residual_relief(contacts[-1])
            finite_units = [u for u in result["units"] if u["processId"] in {"lava_flow", "fluvial_channel_fill"}]
            finite_ok = all(not all(u["active"]) and any(u["active"]) for u in finite_units)
            # The two deepest contacts must not both be almost exact terrain copies.
            copy_like = deep_surface_corr > .985 and correlations[-1] > .995
            featureless = deep_residual_relief < 2.0
            record = {"family": family, "seed": seed, "adjacentSlopeCorrelations": correlations,
                      "deepSurfaceSlopeCorrelation": deep_surface_corr,
                      "deepLinearResidualRelief": deep_residual_relief,
                      "finiteTopologyPreserved": finite_ok, "copyLike": copy_like,
                      "featurelessDeepContact": featureless}
            records.append(record)
            if not finite_ok:
                failures.append({"family": family, "seed": seed, "code": "FiniteTopologyLost"})
            if copy_like:
                failures.append({"family": family, "seed": seed, "code": "DeepContactsCopyModernTerrain",
                                 "correlation": deep_surface_corr})
            if featureless:
                failures.append({"family": family, "seed": seed, "code": "FeaturelessDeepContact",
                                 "linearResidualRelief": deep_residual_relief})
    report = {"schemaVersion": "1.0.0", "terrainFamilies": families,
              "seedsPerFamily": seeds, "terrainCaseCount": len(families)*seeds,
              "failureCount": len(failures), "passed": not failures,
              "failures": failures, "records": records}
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    report = run(here / "process_catalog.json", here.parents[1] / "outputs/geologic_pattern_terrain_robustness.json")
    print(json.dumps({k: v for k, v in report.items() if k not in {"records", "failures"}}, ensure_ascii=False, indent=2))
    if report["failures"]:
        print(json.dumps(report["failures"][:20], ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 2)
