"""GUI/JSON contract for Stage-2 conformable stack construction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..config import EngineConfig
from ..geometry.regular_grid import RegularGrid3D
from .conformable_stack import build_conformable_stack


def materialize_field(spec: dict, ny: int, nx: int, name: str) -> list[list[float]]:
    unknown = sorted(set(spec) - {"constant", "values"})
    if unknown:
        raise ValueError(f"{name} contains unsupported keys: {', '.join(unknown)}")
    if "constant" in spec and "values" in spec:
        raise ValueError(f"{name} cannot define both constant and values")
    if "constant" in spec:
        value = float(spec["constant"])
        return [[value for _ in range(nx)] for _ in range(ny)]
    values = spec.get("values")
    if not isinstance(values, list) or len(values) != ny or any(
            not isinstance(row, list) or len(row) != nx for row in values):
        raise ValueError(f"{name}.values shape must be [ny={ny}][nx={nx}]")
    return [[float(value) for value in row] for row in values]


@dataclass(frozen=True)
class StackLayerSpec:
    unit_id: str
    thickness_field: dict


@dataclass(frozen=True)
class StackBuildSpec:
    top_surface: dict
    layers: tuple[StackLayerSpec, ...]
    deferred_unit_ids: tuple[str, ...] = ()
    zero_thickness_tolerance: float = 1e-9

    @classmethod
    def from_dict(cls, data: dict) -> "StackBuildSpec":
        return cls(dict(data.get("topSurface", {})), tuple(
            StackLayerSpec(str(item.get("unitId", "")), dict(item.get("thicknessField", {})))
            for item in data.get("layers", [])), tuple(data.get("deferredUnitIds", [])),
            float(data.get("zeroThicknessTolerance", 1e-9)))

    def build(self, config: EngineConfig):
        grid = RegularGrid3D.from_extent(config.extent)
        expected = [unit.unit_id for unit in sorted(config.units, key=lambda item: item.order_index)]
        supplied = [layer.unit_id for layer in self.layers]
        deferred = list(self.deferred_unit_ids)
        if len(set(supplied + deferred)) != len(supplied) + len(deferred):
            raise ValueError("stack and deferred unit IDs must be unique")
        if set(supplied + deferred) != set(expected):
            raise ValueError("stack plus deferred units must equal configured units")
        expected_supplied = [unit_id for unit_id in expected if unit_id not in set(deferred)]
        if supplied != expected_supplied:
            raise ValueError(f"stack layer order must match configured order: expected {expected_supplied}")
        top = materialize_field(self.top_surface, grid.ny, grid.nx, "topSurface")
        thickness = [materialize_field(layer.thickness_field, grid.ny, grid.nx,
                                        f"layers[{layer.unit_id}].thicknessField")
                     for layer in self.layers]
        return build_conformable_stack(grid, top, supplied, thickness,
                                       self.zero_thickness_tolerance)


def load_stack_spec(path: str | Path) -> StackBuildSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("stack specification root must be an object")
    return StackBuildSpec.from_dict(data)
