"""Stage-5 structural-kinematics input contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..config import EngineConfig
from ..models import EventType
from ..stratigraphy.stack_spec import materialize_field
from .structural_3d import StructuralOperation


@dataclass(frozen=True)
class StructuralSpec:
    operations: tuple[dict, ...]
    tolerance: float = 1e-9

    @classmethod
    def from_dict(cls, data):
        return cls(tuple(dict(item) for item in data.get("operations", [])),
                   float(data.get("tolerance", 1e-9)))

    def materialize(self, config: EngineConfig, model) -> tuple[StructuralOperation, ...]:
        events = {event.event_id: event for event in config.events}
        valid_sources = {source.source_id for source in config.sources}
        output, orders = [], []
        latest_prestructural = max((event.order_index for event in config.events
                                    if event.event_type not in {EventType.FOLD, EventType.FAULT,
                                                                EventType.INTRUSION}), default=-1)
        model_units = {body.unit_id for body in model.primary_bodies + model.replacement_bodies}
        for item in self.operations:
            event_id, operation = str(item.get("eventId", "")), str(item.get("operation", ""))
            event = events.get(event_id)
            expected = EventType.FOLD if operation == "FoldDisplacementField" else (
                EventType.FAULT if operation == "PlanarFaultSlip" else None)
            if event is None or expected is None or event.event_type != expected:
                raise ValueError(f"structural operation/event mismatch: {event_id}")
            if event.order_index <= latest_prestructural:
                raise ValueError("current staged solver requires structural events after all pre-structural events")
            evidence = tuple(item.get("evidenceSourceIds", []))
            if not evidence or not set(evidence) <= valid_sources:
                raise ValueError(f"structural event {event_id} requires valid evidenceSourceIds")
            affected = tuple(item.get("affectedUnitIds", event.affected_unit_ids))
            if set(affected) != set(event.affected_unit_ids):
                raise ValueError(f"affected units must match configured event {event_id}")
            if set(affected) != model_units:
                raise ValueError("current staged solver requires every modeled unit to receive each structural operator")
            if operation == "FoldDisplacementField":
                field = materialize_field(dict(item.get("verticalDisplacement", {})),
                                          model.grid.ny, model.grid.nx,
                                          "verticalDisplacement")
                parameters = {"verticalDisplacement": field,
                              "evidenceSourceIds": list(evidence)}
            else:
                parameters = {"planeNormal": list(item.get("planeNormal", [])),
                              "planeOffset": float(item.get("planeOffset", 0)),
                              "slipVector": list(item.get("slipVector", [])),
                              "displacement": float(item.get("displacement", 0)),
                              "partition": str(item.get("partition", "positive-side")),
                              "evidenceSourceIds": list(evidence)}
            output.append(StructuralOperation(event_id, operation, affected, parameters))
            orders.append(event.order_index)
        if not output:
            raise ValueError("at least one structural operation is required")
        if orders != sorted(orders) or len(set(orders)) != len(orders):
            raise ValueError("structural operations must follow unique configured event order")
        return tuple(output)


def load_structural_spec(path: str | Path) -> StructuralSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("structural specification root must be an object")
    return StructuralSpec.from_dict(data)
