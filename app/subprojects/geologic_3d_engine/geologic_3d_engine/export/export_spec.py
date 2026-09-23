"""Stage-11 AutoCAD-neutral drafting policy contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UnitDraftingSpec:
    unit_id: str
    display_name: str
    layer_name: str
    rgb: tuple[int, int, int]


@dataclass(frozen=True)
class ExportSpec:
    drawing_id: str
    boundary_layer: str
    units: tuple[UnitDraftingSpec, ...]
    synthetic_disclosure: str
    dwg_version: str = "AC1032"

    @classmethod
    def from_dict(cls,data):
        units=tuple(UnitDraftingSpec(str(x.get("unitId","")),str(x.get("displayName","")),
          str(x.get("layerName","")),tuple(int(v) for v in x.get("rgb",[])))
          for x in data.get("units",[]))
        return cls(str(data.get("drawingId","")),str(data.get("boundaryLayer","")),units,
                   str(data.get("syntheticDisclosure","")),str(data.get("dwgVersion","AC1032")))

    def validate(self,section):
        if not self.drawing_id or not self.boundary_layer or not self.synthetic_disclosure:
            raise ValueError("drawingId, boundaryLayer and syntheticDisclosure are required")
        if self.dwg_version!="AC1032": raise ValueError("Stage 11 requires AutoCAD 2018 DWG AC1032")
        ids=[u.unit_id for u in self.units]
        expected=[u["unitId"] for u in section["unitSections"]]
        if len(set(ids))!=len(ids) or set(ids)!=set(expected):
            raise ValueError("drafting units must uniquely match section units")
        layers=[u.layer_name for u in self.units]
        if len(set(layers))!=len(layers): raise ValueError("unit layer names must be unique")
        for unit in self.units:
            if not unit.display_name or not unit.layer_name or len(unit.rgb)!=3:
                raise ValueError("each unit requires displayName, layerName and RGB")
            if any(v<0 or v>255 for v in unit.rgb): raise ValueError("RGB must be in [0,255]")
        return self


def load_export_spec(path:str|Path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data,dict): raise ValueError("export specification root must be an object")
    return ExportSpec.from_dict(data)
