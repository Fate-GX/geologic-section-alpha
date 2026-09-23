"""Validated Stage-4 compaction input contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..config import EngineConfig
from ..models import EventType
from ..stratigraphy.stack_spec import materialize_field
from .compaction_3d import UnitPorosityState


@dataclass(frozen=True)
class CompactionUnitSpec:
    unit_id: str
    source_porosity: dict
    target_porosity: dict
    evidence_source_ids: tuple[str, ...]


@dataclass(frozen=True)
class CompactionSpec:
    event_id: str
    units: tuple[CompactionUnitSpec, ...]
    anchor: str = "TopSurfaceFixed"
    tolerance: float = 1e-9

    @classmethod
    def from_dict(cls, data: dict) -> "CompactionSpec":
        units = tuple(CompactionUnitSpec(str(item.get("unitId", "")),
                    dict(item.get("sourcePorosity", {})),
                    dict(item.get("targetPorosity", {})),
                    tuple(item.get("evidenceSourceIds", [])))
                    for item in data.get("units", []))
        return cls(str(data.get("eventId", "")), units,
                   str(data.get("anchor", "TopSurfaceFixed")),
                   float(data.get("tolerance", 1e-9)))

    def materialize(self, config: EngineConfig, model) -> tuple[UnitPorosityState, ...]:
        event = next((item for item in config.events if item.event_id == self.event_id), None)
        if event is None or event.event_type != EventType.COMPACTION:
            raise ValueError("compaction eventId must reference a configured Compaction event")
        if self.anchor != "TopSurfaceFixed":
            raise ValueError("only explicit TopSurfaceFixed anchoring is currently supported")
        valid_sources = {source.source_id for source in config.sources}
        states = []
        for item in self.units:
            if not item.evidence_source_ids or not set(item.evidence_source_ids) <= valid_sources:
                raise ValueError(f"unit {item.unit_id} requires valid porosity evidenceSourceIds")
            source = materialize_field(item.source_porosity, model.grid.ny, model.grid.nx,
                                       f"{item.unit_id}.sourcePorosity")
            target = materialize_field(item.target_porosity, model.grid.ny, model.grid.nx,
                                       f"{item.unit_id}.targetPorosity")
            for y in range(model.grid.ny):
                for x in range(model.grid.nx):
                    if not (0 <= target[y][x] <= source[y][x] < 1):
                        raise ValueError("porosity must satisfy 0 <= target <= source < 1")
            states.append(UnitPorosityState(item.unit_id, tuple(map(tuple, source)),
                                            tuple(map(tuple, target)),
                                            item.evidence_source_ids))
        affected = set(event.affected_unit_ids)
        if affected and {state.unit_id for state in states} != affected:
            raise ValueError("compaction units must equal configured affectedUnitIds")
        return tuple(states)


def load_compaction_spec(path: str | Path) -> CompactionSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("compaction specification root must be an object")
    return CompactionSpec.from_dict(data)
