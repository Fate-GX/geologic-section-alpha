"""Stage-7 closed-mesh input contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MeshBuildSpec:
    unit_ids: tuple[str, ...]
    coordinate_frame: str = "SourceMaterialGrid"
    triangulate: bool = True

    @classmethod
    def from_dict(cls, data):
        return cls(tuple(data.get("unitIds", [])),
                   str(data.get("coordinateFrame", "SourceMaterialGrid")),
                   bool(data.get("triangulate", True)))

    def validate(self, intrusion_model):
        if self.coordinate_frame != "SourceMaterialGrid":
            raise ValueError("Stage 7 currently supports only SourceMaterialGrid")
        if not self.triangulate:
            raise ValueError("triangulation is required for mesh validation")
        present = {label for layer in intrusion_model.labels_zyx for row in layer
                   for label in row if label is not None}
        if len(set(self.unit_ids)) != len(self.unit_ids) or set(self.unit_ids) != present:
            raise ValueError("unitIds must uniquely equal all represented material units")
        return self


def load_mesh_spec(path: str | Path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("mesh specification root must be an object")
    return MeshBuildSpec.from_dict(data)
