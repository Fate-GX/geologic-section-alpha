"""Validated JSON contract for Stage-3 stratigraphic event operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..config import EngineConfig
from ..models import EventType
from ..stratigraphy.stack_spec import materialize_field
from .stratigraphic_events import (EventVolumeModel, apply_erosion,
                                   build_deposit_on_surface, build_lens_in_host,
                                   from_conformable_stack)


@dataclass(frozen=True)
class EventOperationSpec:
    event_id: str
    operation: str
    parameters: dict


@dataclass(frozen=True)
class Stage3EventSpec:
    operations: tuple[EventOperationSpec, ...]
    zero_thickness_tolerance: float = 1e-9

    @classmethod
    def from_dict(cls, data: dict) -> "Stage3EventSpec":
        operations = []
        for item in data.get("operations", []):
            parameters = {key: value for key, value in item.items()
                          if key not in {"eventId", "operation"}}
            operations.append(EventOperationSpec(str(item.get("eventId", "")),
                                                  str(item.get("operation", "")),
                                                  parameters))
        return cls(tuple(operations), float(data.get("zeroThicknessTolerance", 1e-9)))

    def apply(self, config: EngineConfig, stack) -> EventVolumeModel:
        if not self.operations:
            raise ValueError("at least one Stage-3 operation is required")
        events = {event.event_id: event for event in config.events}
        event_order = []
        model = from_conformable_stack(stack)
        introduced = set()
        configured_units = {unit.unit_id for unit in config.units}
        expected_type = {"Erosion": EventType.EROSION,
                         "ErosionFill": EventType.DEPOSITION,
                         "Onlap": EventType.DEPOSITION,
                         "Lens": EventType.DEPOSITION}
        for operation in self.operations:
            if operation.event_id not in events:
                raise ValueError(f"unknown eventId: {operation.event_id}")
        configured_order = [events[operation.event_id].order_index
                            for operation in self.operations]
        if configured_order != sorted(configured_order) or len(set(configured_order)) != len(configured_order):
            raise ValueError("Stage-3 operations must follow unique configured event order")
        for operation in self.operations:
            if operation.operation not in expected_type:
                raise ValueError(f"unsupported Stage-3 operation: {operation.operation}")
            event = events.get(operation.event_id)
            if event is None:
                raise ValueError(f"unknown eventId: {operation.event_id}")
            if event.event_type != expected_type[operation.operation]:
                raise ValueError(f"event type mismatch for {operation.event_id}")
            event_order.append(event.order_index)
            p = operation.parameters
            if operation.operation == "Erosion":
                surface = materialize_field(dict(p.get("surface", {})), model.grid.ny,
                                            model.grid.nx, "surface")
                model = apply_erosion(model, surface, operation.event_id,
                                      self.zero_thickness_tolerance)
            elif operation.operation in {"ErosionFill", "Onlap"}:
                unit_id = str(p.get("unitId", ""))
                self._validate_new_unit(unit_id, configured_units, introduced, event)
                thickness = materialize_field(dict(p.get("thicknessField", {})), model.grid.ny,
                                              model.grid.nx, "thicknessField")
                model = build_deposit_on_surface(model, unit_id, thickness,
                                                 operation.event_id, operation.operation,
                                                 self.zero_thickness_tolerance)
                introduced.add(unit_id)
            else:
                unit_id, host = str(p.get("unitId", "")), str(p.get("hostUnitId", ""))
                self._validate_new_unit(unit_id, configured_units, introduced, event)
                if host not in configured_units:
                    raise ValueError(f"unknown lens host unit: {host}")
                bottom = materialize_field(dict(p.get("bottomSurface", {})), model.grid.ny,
                                           model.grid.nx, "bottomSurface")
                thickness = materialize_field(dict(p.get("thicknessField", {})), model.grid.ny,
                                              model.grid.nx, "thicknessField")
                model = build_lens_in_host(model, host, unit_id, bottom, thickness,
                                           operation.event_id,
                                           bool(p.get("allowDomainBoundaryExit", False)),
                                           self.zero_thickness_tolerance)
                introduced.add(unit_id)
        return model

    @staticmethod
    def _validate_new_unit(unit_id, configured_units, introduced, event):
        if not unit_id or unit_id not in configured_units:
            raise ValueError(f"unknown introduced unit: {unit_id}")
        if unit_id in introduced:
            raise ValueError(f"unit introduced more than once: {unit_id}")
        if event.affected_unit_ids and unit_id not in event.affected_unit_ids:
            raise ValueError(f"unit {unit_id} is not affected by event {event.event_id}")


def load_event_spec(path: str | Path) -> Stage3EventSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("event specification root must be an object")
    return Stage3EventSpec.from_dict(data)
