"""Universal, parameter-explicit compaction and diagenesis operations."""

from __future__ import annotations

import math
from typing import Sequence


def _porosity(value: float, name: str) -> float:
    result = float(value)
    if not 0.0 <= result < 1.0:
        raise ValueError(f"{name} must be in [0, 1)")
    return result


def athy_porosity(depth: float, depositional_porosity: float,
                  compaction_coefficient: float) -> float:
    depth, coefficient = float(depth), float(compaction_coefficient)
    phi0 = _porosity(depositional_porosity, "depositional_porosity")
    if depth < 0 or coefficient < 0:
        raise ValueError("depth and compaction coefficient must be non-negative")
    return phi0 * math.exp(-coefficient * depth)


def solid_thickness(bulk_thickness: float, porosity: float) -> float:
    thickness = float(bulk_thickness)
    if thickness < 0:
        raise ValueError("bulk thickness must be non-negative")
    return thickness * (1.0 - _porosity(porosity, "porosity"))


def bulk_thickness_from_solid(solid: float, porosity: float) -> float:
    solid = float(solid)
    if solid < 0:
        raise ValueError("solid thickness must be non-negative")
    return solid / (1.0 - _porosity(porosity, "porosity"))


def transform_thickness(thickness: float, source_porosity: float,
                        target_porosity: float) -> dict:
    source = _porosity(source_porosity, "source_porosity")
    target = _porosity(target_porosity, "target_porosity")
    solid = solid_thickness(thickness, source)
    transformed = bulk_thickness_from_solid(solid, target)
    return {"sourceThickness": float(thickness), "targetThickness": transformed,
            "sourcePorosity": source, "targetPorosity": target,
            "solidThickness": solid, "solidVolumePreserved": True}


def compact_stack(top_surface: Sequence[float], depositional_thickness: Sequence[Sequence[float]],
                  depositional_porosity: Sequence[Sequence[float]],
                  current_porosity: Sequence[Sequence[float]]) -> list[dict]:
    top = [float(value) for value in top_surface]
    if not top:
        raise ValueError("top surface must not be empty")
    if not (len(depositional_thickness) == len(depositional_porosity) == len(current_porosity)):
        raise ValueError("layer collections must have equal length")
    units, current_top = [], list(top)
    for layer_index, (thicknesses, initial_phis, current_phis) in enumerate(zip(
            depositional_thickness, depositional_porosity, current_porosity)):
        if not (len(thicknesses) == len(initial_phis) == len(current_phis) == len(top)):
            raise ValueError("every layer field must match the top-surface sample count")
        compacted, solid = [], []
        for thickness, initial_phi, current_phi in zip(thicknesses, initial_phis, current_phis):
            result = transform_thickness(thickness, initial_phi, current_phi)
            if result["targetThickness"] > result["sourceThickness"] + 1e-9:
                raise ValueError("compaction target porosity cannot exceed source porosity")
            compacted.append(result["targetThickness"]); solid.append(result["solidThickness"])
        bottom = [surface - thickness for surface, thickness in zip(current_top, compacted)]
        units.append({"unitIndex": layer_index, "top": list(current_top), "bottom": bottom,
                      "compactedThickness": compacted, "solidThickness": solid,
                      "active": [value > 0 for value in compacted]})
        current_top = bottom
    return units


def validate_compacted_stack(units: Sequence[dict], tolerance: float = 1e-9) -> dict:
    errors = []
    for index, unit in enumerate(units):
        for sample, (top, bottom, compacted, solid) in enumerate(zip(
                unit["top"], unit["bottom"], unit["compactedThickness"], unit["solidThickness"])):
            if compacted < -tolerance or bottom > top + tolerance:
                errors.append({"code": "NegativeThickness", "unitIndex": index,
                               "sampleIndex": sample})
            if solid > compacted + tolerance:
                errors.append({"code": "SolidExceedsBulkVolume", "unitIndex": index,
                               "sampleIndex": sample})
        if index and any(abs(previous - current) > tolerance for previous, current in zip(
                units[index - 1]["bottom"], unit["top"])):
            errors.append({"code": "UnsharedContact", "unitIndex": index})
    return {"passed": not errors, "errors": errors,
            "sharedContactStack": True, "independentContactWarpingAllowed": False}


def classify_diagenetic_evidence(evidence: dict) -> dict:
    processes = []
    if evidence.get("porosityLossWithBurial") or evidence.get("effectiveStressHistory"):
        processes.append("MechanicalCompactionSupported")
    if evidence.get("cementVolumeMeasured") or evidence.get("cementPetrographyObserved"):
        processes.append("CementationSupported")
    if evidence.get("dissolutionTextureObserved") or evidence.get("secondaryPorosityMeasured"):
        processes.append("DissolutionSupported")
    if evidence.get("overpressureObserved"):
        processes.append("DisequilibriumCompactionPossible")
    state = processes[0] if len(processes) == 1 else (
        "MultipleProcessesSupported" if processes else "Unresolved")
    return {"state": state, "supportedProcesses": processes,
            "lithologyNameAloneIsSufficient": False,
            "requiresHistoryDependentModel": bool(evidence.get("overpressureObserved") or
                                                    evidence.get("temperatureHistoryAvailable"))}
