"""Stage-10 arbitrary section-plane contract."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SectionSpec:
    section_id: str
    origin: tuple[float, float, float]
    normal: tuple[float, float, float]
    u_direction: tuple[float, float, float]
    u_range: tuple[float, float]
    v_range: tuple[float, float]
    tolerance: float = 1e-8

    @classmethod
    def from_dict(cls, data):
        return cls(str(data.get("sectionId", "")), tuple(map(float, data.get("origin", []))),
            tuple(map(float, data.get("normal", []))),
            tuple(map(float, data.get("uDirection", []))),
            tuple(map(float, data.get("uRange", []))), tuple(map(float, data.get("vRange", []))),
            float(data.get("tolerance", 1e-8)))

    def validate(self):
        if not self.section_id:
            raise ValueError("sectionId is required")
        if any(len(v) != 3 for v in (self.origin, self.normal, self.u_direction)):
            raise ValueError("origin, normal and uDirection must be 3D vectors")
        if len(self.u_range) != 2 or len(self.v_range) != 2:
            raise ValueError("uRange and vRange must contain two values")
        if self.u_range[1] <= self.u_range[0] or self.v_range[1] <= self.v_range[0]:
            raise ValueError("section ranges must be increasing")
        if self.tolerance <= 0:
            raise ValueError("tolerance must be positive")
        n = _norm(self.normal); u = _norm(self.u_direction)
        if n == 0 or u == 0:
            raise ValueError("normal and uDirection must be non-zero")
        dot = sum(a*b for a,b in zip(self.normal, self.u_direction)) / (n*u)
        if abs(dot) > 1e-8:
            raise ValueError("uDirection must be perpendicular to normal")
        return self

    def basis(self):
        n = _unit(self.normal); u = _unit(self.u_direction)
        v = (n[1]*u[2]-n[2]*u[1], n[2]*u[0]-n[0]*u[2], n[0]*u[1]-n[1]*u[0])
        return u, v, n


def _norm(v): return math.sqrt(sum(x*x for x in v))
def _unit(v):
    length = _norm(v)
    return tuple(x/length for x in v)


def load_section_spec(path: str | Path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("section specification root must be an object")
    return SectionSpec.from_dict(data)
