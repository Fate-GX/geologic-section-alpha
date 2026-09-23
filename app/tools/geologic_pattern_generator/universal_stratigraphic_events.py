"""Reusable stratigraphic event operations and evidence classification."""

from __future__ import annotations

from typing import Sequence


def _vector(values: Sequence[float], name: str) -> list[float]:
    result = [float(value) for value in values]
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


def truncate_by_erosion(units: Sequence[dict], erosion_surface: Sequence[float],
                        tolerance: float = 1e-9) -> dict:
    """Truncate pre-existing units; never extend old material above erosion."""
    surface = _vector(erosion_surface, "erosion_surface")
    truncated = []
    total_removed = [0.0] * len(surface)
    for unit in units:
        top = _vector(unit["top"], "top")
        bottom = _vector(unit["bottom"], "bottom")
        if len(top) != len(surface) or len(bottom) != len(surface):
            raise ValueError("all surfaces must have equal sample counts")
        if any(b > t + tolerance for t, b in zip(top, bottom)):
            raise ValueError("input unit has negative thickness")
        retained_top = []
        active = []
        removed = []
        for index, (t, b, erosion) in enumerate(zip(top, bottom, surface)):
            retained = max(0.0, min(t, erosion) - b)
            old = max(0.0, t - b)
            new_top = b + retained
            retained_top.append(new_top)
            active.append(retained > tolerance)
            removed.append(old - retained)
            total_removed[index] += old - retained
        truncated.append({**unit, "top": retained_top, "bottom": bottom,
                          "active": active, "removedThickness": removed,
                          "truncationEvent": "Erosion"})
    return {"units": truncated, "erosionSurface": surface,
            "totalRemovedThickness": total_removed,
            "operation": "TruncateOlderUnitsBeforeYoungerDeposition"}


def deposit_on_surface(unit_id: str, base_surface: Sequence[float],
                       thickness: Sequence[float], tolerance: float = 1e-9) -> dict:
    """Deposit a younger unit on an event surface; zero thickness is explicit absence."""
    bottom = _vector(base_surface, "base_surface")
    field = _vector(thickness, "thickness")
    if len(bottom) != len(field):
        raise ValueError("base surface and thickness must have equal sample counts")
    if any(value < -tolerance for value in field):
        raise ValueError("depositional thickness cannot be negative")
    field = [max(0.0, value) for value in field]
    return {"unitId": unit_id, "bottom": bottom,
            "top": [base + value for base, value in zip(bottom, field)],
            "active": [value > tolerance for value in field],
            "depositionalRelation": "OnlapOrCoverOnEventSurface"}


def validate_erosional_event(result: dict, tolerance: float = 1e-9) -> dict:
    errors = []
    surface = result.get("erosionSurface", [])
    for unit_index, unit in enumerate(result.get("units", [])):
        for sample_index, (top, bottom, erosion, active) in enumerate(
                zip(unit["top"], unit["bottom"], surface, unit["active"])):
            if active and top > erosion + tolerance:
                errors.append({"code": "OldMaterialAboveErosionSurface",
                               "unitIndex": unit_index, "sampleIndex": sample_index})
            if bottom > top + tolerance:
                errors.append({"code": "NegativeRetainedThickness",
                               "unitIndex": unit_index, "sampleIndex": sample_index})
    return {"passed": not errors, "errors": errors,
            "oldContactsMayCrossErosionSurface": False}


def classify_missing_interval(evidence: dict) -> dict:
    """Classify an absent interval without treating absence alone as erosion."""
    if not evidence.get("penetratedExpectedDepth", True):
        state = "Nonpenetration"
    elif not evidence.get("recordQualityComplete", True):
        state = "MissingRecord"
    else:
        erosion = bool(evidence.get("erosionalSurfaceObserved") or
                       evidence.get("basalLagObserved") or
                       evidence.get("truncationObserved"))
        pinchout = bool(evidence.get("lateralThicknessConvergence"))
        nondeposition = bool(evidence.get("hiatusAgeEvidence"))
        supported = [name for name, value in (("ErosionSupported", erosion),
                                              ("PinchoutSupported", pinchout),
                                              ("NondepositionSupported", nondeposition)) if value]
        state = supported[0] if len(supported) == 1 else (
            "ConflictingEvidence" if len(supported) > 1 else "Ambiguous")
    return {"state": state, "forcedInterpretation": False,
            "absenceAloneProvesErosion": False, "evidence": dict(evidence)}


def validate_event_sequence(events: Sequence[dict]) -> dict:
    """Validate explicit chronological events and their required inputs."""
    allowed = {"Deposition", "Erosion", "Nondeposition", "Fault"}
    errors = []
    seen_ids = set()
    material_exists = False
    for index, event in enumerate(events):
        event_id = event.get("eventId")
        event_type = event.get("eventType")
        if not event_id or event_id in seen_ids:
            errors.append({"code": "MissingOrDuplicateEventId", "eventIndex": index})
        seen_ids.add(event_id)
        if event_type not in allowed:
            errors.append({"code": "UnknownEventType", "eventIndex": index})
        if event_type == "Erosion" and not material_exists:
            errors.append({"code": "ErosionBeforeAnyDeposition", "eventIndex": index})
        if event_type == "Deposition":
            material_exists = True
    return {"passed": not errors, "errors": errors,
            "chronologyPreserved": True, "eventCount": len(events)}
