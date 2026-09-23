"""Stochastic lithology method selection and training-image diagnostics.

This module implements portable validation machinery learned from ArchPy,
MPSlib, GSTools and categorical indicator simulation. It intentionally does not
reimplement their numerical solvers.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Hashable, Iterable, Sequence


def indicator_vector(category: Hashable, categories: Sequence[Hashable]) -> list[int]:
    """Categorical indicator I(u;k): one for the observed category, zero otherwise."""
    if category not in categories:
        raise ValueError("category is outside the declared vocabulary")
    if len(set(categories)) != len(categories):
        raise ValueError("category vocabulary contains duplicates")
    return [1 if category == candidate else 0 for candidate in categories]


def classify_surface_constraint(exact_elevation=None, lower_bound=None,
                                upper_bound=None) -> dict:
    """Preserve equality and inequality contact evidence without inventing a contact."""
    supplied = [exact_elevation is not None, lower_bound is not None, upper_bound is not None]
    if exact_elevation is not None and any(supplied[1:]):
        raise ValueError("exact and inequality constraints cannot be mixed")
    if exact_elevation is not None:
        return {"constraintType": "Equality", "value": float(exact_elevation)}
    if lower_bound is not None and upper_bound is not None:
        low, high = float(lower_bound), float(upper_bound)
        if low > high:
            raise ValueError("lower bound exceeds upper bound")
        return {"constraintType": "Interval", "lower": low, "upper": high}
    if lower_bound is not None:
        return {"constraintType": "LowerBound", "lower": float(lower_bound)}
    if upper_bound is not None:
        return {"constraintType": "UpperBound", "upper": float(upper_bound)}
    return {"constraintType": "Unresolved"}


def validate_hierarchical_records(records: Iterable[dict]) -> dict:
    """Require property -> facies -> unit containment and prevent cross-unit pooling."""
    errors = []
    facies_units = defaultdict(set)
    for index, record in enumerate(records):
        unit = record.get("unitId")
        facies = record.get("faciesId")
        if not unit:
            errors.append({"code": "MissingUnit", "recordIndex": index})
        if record.get("propertyValue") is not None and not facies:
            errors.append({"code": "PropertyWithoutFacies", "recordIndex": index})
        if facies and unit:
            facies_units[facies].add(unit)
    partitions = [{"faciesId": facies, "unitIds": sorted(units),
                   "mustSimulateSeparatelyByUnit": len(units) > 1}
                  for facies, units in sorted(facies_units.items())]
    return {"passed": not errors, "errors": errors, "faciesPartitions": partitions,
            "dependencyOrder": ["Unit", "FaciesWithinUnit", "PropertyWithinFacies"]}


def _shape_and_getter(grid):
    nz = len(grid)
    if nz == 0:
        raise ValueError("grid must not be empty")
    ny = len(grid[0])
    nx = len(grid[0][0]) if ny else 0
    if nx == 0 or any(len(layer) != ny or any(len(row) != nx for row in layer)
                      for layer in grid):
        raise ValueError("grid must be a rectangular [z][y][x] array")
    return (nz, ny, nx), lambda z, y, x: grid[z][y][x]


def training_image_signature(grid, categories: Sequence[Hashable]) -> dict:
    """Extract proportions and directional one-cell transition probabilities."""
    shape, value = _shape_and_getter(grid)
    if len(set(categories)) != len(categories):
        raise ValueError("category vocabulary contains duplicates")
    counts = Counter()
    transitions = {axis: Counter() for axis in ("x", "y", "z")}
    nz, ny, nx = shape
    for z in range(nz):
        for y in range(ny):
            for x in range(nx):
                current = value(z, y, x)
                if current not in categories:
                    raise ValueError("training image contains an undeclared category")
                counts[current] += 1
                if x + 1 < nx:
                    transitions["x"][(current, value(z, y, x + 1))] += 1
                if y + 1 < ny:
                    transitions["y"][(current, value(z, y + 1, x))] += 1
                if z + 1 < nz:
                    transitions["z"][(current, value(z + 1, y, x))] += 1
    total = sum(counts.values())
    proportions = {str(category): counts[category] / total for category in categories}
    probabilities = {}
    for axis, pairs in transitions.items():
        origin_totals = Counter()
        for (origin, _), count in pairs.items():
            origin_totals[origin] += count
        probabilities[axis] = {
            f"{origin}->{destination}": (pairs[(origin, destination)] / origin_totals[origin]
                                         if origin_totals[origin] else None)
            for origin in categories for destination in categories
        }
    return {"shapeZYX": list(shape), "proportions": proportions,
            "directionalTransitions": probabilities,
            "capturesMultiplePointGeometry": False,
            "note": "Pair transitions are screening diagnostics, not a substitute for MPS patterns."}


def compare_training_image_signatures(candidate: dict, evidence: dict) -> dict:
    """Return transparent distances; the caller must supply use-case tolerances."""
    keys = sorted(set(candidate["proportions"]) | set(evidence["proportions"]))
    proportion_l1 = sum(abs(candidate["proportions"].get(key, 0.0) -
                            evidence["proportions"].get(key, 0.0)) for key in keys)
    transition_l1 = {}
    for axis in ("x", "y", "z"):
        first = candidate["directionalTransitions"].get(axis, {})
        second = evidence["directionalTransitions"].get(axis, {})
        values = []
        for key in set(first) | set(second):
            a, b = first.get(key), second.get(key)
            if a is not None and b is not None:
                values.append(abs(a - b))
        transition_l1[axis] = sum(values) / len(values) if values else None
    return {"proportionL1": proportion_l1, "meanDirectionalTransitionL1": transition_l1,
            "automaticallyAuthorized": False,
            "reason": "Scale, orientation, environment, connectivity and higher-order patterns also require evidence."}


def experimental_semivariance(values: Sequence[float], pairs_by_lag: dict) -> dict:
    """Compute gamma(h)=1/(2N) sum[Z(u+h)-Z(u)]^2 for supplied lag pairs."""
    data = [float(item) for item in values]
    result = {}
    for lag, pairs in pairs_by_lag.items():
        checked = []
        for first, second in pairs:
            if not (0 <= first < len(data) and 0 <= second < len(data)):
                raise ValueError("variogram pair index is outside the value array")
            checked.append((data[second] - data[first]) ** 2)
        result[str(lag)] = 0.5 * sum(checked) / len(checked) if checked else None
    return result


def select_stochastic_method(evidence: dict) -> dict:
    """Evidence-gated solver selection; never promote visual preference to evidence."""
    blockers = []
    methods = []
    if not evidence.get("unitDomainDefined"):
        blockers.append("UnitDomainUndefined")
    if evidence.get("singleFaciesOnly"):
        methods.append("Homogeneous")
    if evidence.get("categoryProportions") and evidence.get("indicatorVariogram"):
        methods.append("SequentialIndicatorSimulation")
    if evidence.get("latentCovarianceModels") and evidence.get("truncationRule"):
        methods.append("TruncatedPluriGaussian")
    training_keys = ("trainingImage", "trainingImageProvenance", "scaleCompatibility",
                     "orientationCompatibility", "environmentCompatibility",
                     "trainingImageDiagnosticsPassed")
    if all(evidence.get(key) for key in training_keys):
        methods.append("MultiplePointStatistics")
    elif evidence.get("trainingImage"):
        blockers.append("TrainingImageApplicabilityUnverified")
    if evidence.get("continuousProperty") and evidence.get("covarianceModel"):
        methods.append("ConditionedRandomFieldWithinFacies")
    if blockers and "UnitDomainUndefined" in blockers:
        methods = []
    return {"authorizedMethods": methods, "blockers": blockers,
            "selectionRequired": len(methods) > 1,
            "hierarchy": "UnitsThenFaciesThenProperties",
            "solverOutputBypassesGeologyGates": False}
