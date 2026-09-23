from __future__ import annotations

import csv
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ProcessRule:
    process_id: str
    geometry_family: str
    parameter_ranges: Mapping[str, Sequence[float]]
    required_evidence: tuple[str, ...]
    source_ids: tuple[str, ...]
    stack_supported: bool

    @classmethod
    def from_record(cls, record):
        return cls(record["processId"], record["geometryFamily"], record["parameters"],
                   tuple(record["requiredEvidence"]), tuple(record["sourceIds"]),
                   record.get("stackEngineSupported", True))


def load_catalog(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["processId"]: ProcessRule.from_record(r) for r in data["processes"]}


def validate_parameters(rule: ProcessRule, parameters: Mapping[str, float], evidence_tags: Sequence[str]):
    errors = []
    missing_evidence = sorted(set(rule.required_evidence) - set(evidence_tags))
    if missing_evidence:
        errors.append({"code": "MissingEvidence", "values": missing_evidence})
    if not rule.stack_supported:
        errors.append({"code": "RequiresDedicatedTopologyEngine"})
    for name, bounds in rule.parameter_ranges.items():
        if name not in parameters:
            errors.append({"code": "MissingParameter", "parameter": name})
        elif not bounds[0] <= float(parameters[name]) <= bounds[1]:
            errors.append({"code": "ParameterOutOfRange", "parameter": name,
                           "value": parameters[name], "allowed": bounds})
    if "start" in parameters and "end" in parameters and parameters["start"] >= parameters["end"]:
        errors.append({"code": "InvalidExtent", "message": "start must be less than end"})
    if "peak" in parameters and "start" in parameters and "end" in parameters:
        if not parameters["start"] < parameters["peak"] < parameters["end"]:
            errors.append({"code": "PeakOutsideExtent"})
    if rule.geometry_family == "source_directed_wedge" and "source" in parameters:
        if not parameters["start"] <= parameters["source"] <= parameters["end"]:
            errors.append({"code": "SourceOutsideExtent"})
    return errors


def _taper(u, start, end, left_power=1.0, right_power=1.0):
    if u <= start or u >= end:
        return 0.0
    p = (u - start) / (end - start)
    peak = left_power / (left_power + right_power)
    normalizer = peak ** left_power * (1.0 - peak) ** right_power
    return p ** left_power * (1.0 - p) ** right_power / normalizer


def thickness(rule: ProcessRule, u: float, p: Mapping[str, float]):
    family = rule.geometry_family
    if family == "finite_asymmetric_lobe":
        return p["maximum"] * _taper(u, p["start"], p["end"], p["left_power"], p["right_power"])
    if family == "channel_lens":
        if u <= p["start"] or u >= p["end"]:
            return 0.0
        width = p["left_width"] if u <= p["peak"] else p["right_width"]
        return p["maximum"] * math.exp(-((u - p["peak"]) / width) ** 2) * _taper(u, p["start"], p["end"])
    if family == "source_directed_wedge":
        if u <= p["start"] or u >= p["end"]:
            return 0.0
        return p["maximum"] * math.exp(-p["decay"] * abs(u - p["source"])) * _taper(u, p["start"], p["end"], .5, 1.5)
    if family == "source_attenuating_drape":
        width = p["upwind_width"] if u <= p["source"] else p["downwind_width"]
        return p["minimum"] + p["amplitude"] * math.exp(-((u - p["source"]) / width) ** 2)
    if family == "accommodation_drape":
        return p["minimum"] + p["amplitude"] * math.exp(-((u - p["center"]) / p["width"]) ** 2)
    raise ValueError(f"Unsupported geometry family: {family}")


def generate(config: Mapping, terrain_rows: Sequence[Mapping], catalog: Mapping[str, ProcessRule]):
    x = [float(r["distance_m"]) for r in terrain_rows]
    current_top = [float(r["elevation_m"]) for r in terrain_rows]
    if len(x) < 2 or any(x[i] <= x[i-1] for i in range(1, len(x))):
        raise ValueError("Terrain x coordinates must be strictly increasing")
    span = x[-1] - x[0]
    units, errors = [], []
    for index, spec in enumerate(config["units"]):
        rule = catalog.get(spec["processId"])
        if rule is None:
            errors.append({"unitId": spec["unitId"], "code": "UnknownProcess"})
            continue
        unit_errors = validate_parameters(rule, spec["parameters"], spec.get("evidenceTags", []))
        if unit_errors:
            errors.extend({"unitId": spec["unitId"], **e} for e in unit_errors)
            continue
        values = [max(0.0, thickness(rule, (px-x[0])/span, spec["parameters"])) for px in x]
        bottom = [top-v for top, v in zip(current_top, values)]
        units.append({"unitId": spec["unitId"], "processId": rule.process_id,
                      "sourceIds": sorted(set(rule.source_ids) | set(spec.get("sourceIds", []))),
                      "top": list(current_top), "bottom": bottom,
                      "active": [v > 1e-9 for v in values]})
        current_top = bottom
    quality = validate_model_quality(x, [float(r["elevation_m"]) for r in terrain_rows], units,
                                     config.get("qualityPolicy", {}))
    errors.extend(quality["errors"])
    return {"schemaVersion": "1.0.0", "profileId": config["profileId"],
            "synthetic": True, "x": x, "units": units, "errors": errors,
            "quality": quality, "passed": not errors}


def _slope_correlation(a, b):
    da = [y-x for x, y in zip(a, a[1:])]
    db = [y-x for x, y in zip(b, b[1:])]
    try:
        return statistics.correlation(da, db)
    except statistics.StatisticsError:
        return 1.0


def _linear_residual_relief(values):
    residuals = [v - (values[0] + (values[-1]-values[0])*i/(len(values)-1))
                 for i, v in enumerate(values)]
    return max(residuals) - min(residuals)


def validate_model_quality(x, terrain_y, units, policy):
    if not policy.get("antiMonotonyRequired", False):
        return {"evaluated": False, "errors": []}
    errors = []
    if not units:
        return {"evaluated": True, "errors": [{"code": "NoGeneratedUnits"}]}
    deep = units[-1]["bottom"]
    deep_relief = _linear_residual_relief(deep)
    terrain_deep_corr = abs(_slope_correlation(terrain_y, deep))
    adjacent_corr = abs(_slope_correlation(units[-1]["top"], deep))
    minimum_relief = float(policy.get("minimumDeepResidualRelief", 2.0))
    max_corr = float(policy.get("maxCopyLikeSlopeCorrelation", .995))
    finite_present = any(any(u["active"]) and not all(u["active"]) for u in units)
    if deep_relief < minimum_relief:
        errors.append({"code": "FeaturelessDeepContact", "actual": deep_relief, "minimum": minimum_relief})
    if terrain_deep_corr > max_corr and adjacent_corr > max_corr:
        errors.append({"code": "DeepContactsCopyModernTerrain", "terrainDeepCorrelation": terrain_deep_corr,
                       "adjacentCorrelation": adjacent_corr, "maximum": max_corr})
    if policy.get("requireFiniteBody", False) and not finite_present:
        errors.append({"code": "RequiredFiniteBodyMissing"})
    return {"evaluated": True, "deepLinearResidualRelief": deep_relief,
            "terrainDeepSlopeCorrelation": terrain_deep_corr,
            "deepAdjacentSlopeCorrelation": adjacent_corr,
            "finiteBodyPresent": finite_present, "errors": errors}


def read_terrain(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_outputs(result: Mapping, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "canonical_model.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "canonical_boundaries.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["unit_id", "process_id", "point_index", "distance_m", "top_y", "bottom_y", "active"])
        writer.writeheader()
        for unit in result["units"]:
            for i, px in enumerate(result["x"]):
                writer.writerow({"unit_id": unit["unitId"], "process_id": unit["processId"], "point_index": i,
                                 "distance_m": px, "top_y": unit["top"][i], "bottom_y": unit["bottom"][i],
                                 "active": unit["active"][i]})
    validation = {"passed": result["passed"], "errorCount": len(result["errors"]),
                  "unitCount": len(result["units"]), "syntheticLabelRequired": True,
                  "quality": result.get("quality"), "errors": result["errors"]}
    (output_dir / "validation_report.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    return validation
