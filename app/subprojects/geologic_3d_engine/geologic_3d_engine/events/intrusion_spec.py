"""Validated Stage-6 intrusion input contract."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from ..models import EventType
from .intrusion_3d import IntrusionOperation


@dataclass(frozen=True)
class IntrusionSpec:
    operations: tuple[dict, ...]

    @classmethod
    def from_dict(cls, data):
        return cls(tuple(dict(item) for item in data.get("operations", [])))

    def materialize(self, config, structural_model):
        if not self.operations:
            raise ValueError("at least one intrusion operation is required")
        events = {event.event_id: event for event in config.events}
        sources = {source.source_id for source in config.sources}
        units = {unit.unit_id for unit in config.units}
        existing = {body.unit_id for body in structural_model.source_model.primary_bodies +
                    structural_model.source_model.replacement_bodies}
        output, orders, introduced = [], [], set()
        for item in self.operations:
            event_id, unit_id = str(item.get("eventId", "")), str(item.get("unitId", ""))
            event = events.get(event_id)
            if event is None or event.event_type != EventType.INTRUSION:
                raise ValueError(f"intrusion event mismatch: {event_id}")
            hosts = tuple(item.get("hostUnitIds", [])); evidence = tuple(item.get("evidenceSourceIds", []))
            if unit_id not in units or unit_id in existing or unit_id in introduced:
                raise ValueError(f"intrusion unit must be a new configured unit: {unit_id}")
            if not hosts or not set(hosts) <= existing | introduced:
                raise ValueError("hostUnitIds must reference existing modeled units")
            if set(event.affected_unit_ids) != set(hosts) | {unit_id}:
                raise ValueError("intrusion event affectedUnitIds must equal intrusion plus hosts")
            if not evidence or not set(evidence) <= sources:
                raise ValueError("intrusion requires valid evidenceSourceIds")
            style, geometry = str(item.get("intrusionStyle", "")), str(item.get("geometryType", ""))
            if style not in {"Dike", "Sill", "Plug", "Pluton"}:
                raise ValueError("unsupported intrusionStyle")
            if geometry not in {"Ellipsoid", "PlanarSheet"}:
                raise ValueError("unsupported intrusion geometryType")
            if (style in {"Dike", "Sill"}) != (geometry == "PlanarSheet"):
                raise ValueError("Dike/Sill require PlanarSheet; Plug/Pluton require Ellipsoid")
            parameters = _parameters(item, geometry)
            output.append(IntrusionOperation(event_id, unit_id, style, geometry, hosts,
                          parameters, bool(item.get("allowDomainBoundaryExit", False)), evidence))
            orders.append(event.order_index); introduced.add(unit_id)
        if orders != sorted(orders) or len(set(orders)) != len(orders):
            raise ValueError("intrusions must follow unique configured event order")
        latest_other = max((event.order_index for event in config.events
                            if event.event_type != EventType.INTRUSION), default=-1)
        if min(orders) <= latest_other:
            raise ValueError("current staged solver requires intrusions after prior event classes")
        return tuple(output)


def _parameters(item, geometry):
    if geometry == "Ellipsoid":
        center, axes = list(item.get("center", [])), list(item.get("semiAxes", []))
        if len(center) != 3 or len(axes) != 3 or any(float(value) <= 0 for value in axes):
            raise ValueError("Ellipsoid requires center and positive semiAxes vectors")
        return {"center": list(map(float, center)), "semiAxes": list(map(float, axes))}
    normal, slip = list(item.get("planeNormal", [])), float(item.get("halfThickness", 0))
    if len(normal) != 3 or math.sqrt(sum(float(v) ** 2 for v in normal)) == 0 or slip <= 0:
        raise ValueError("PlanarSheet requires non-zero planeNormal and positive halfThickness")
    result = {"planeNormal": list(map(float, normal)),
              "planeOffset": float(item.get("planeOffset", 0)), "halfThickness": slip}
    if "relationshipEvidence" in item:
        result["relationshipEvidence"] = str(item["relationshipEvidence"])
    return result


def load_intrusion_spec(path: str | Path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("intrusion specification root must be an object")
    return IntrusionSpec.from_dict(data)
