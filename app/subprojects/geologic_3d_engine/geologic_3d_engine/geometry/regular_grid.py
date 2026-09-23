"""Auditable regular Cartesian grid used by the initial 3D engine stages."""

from __future__ import annotations

from dataclasses import dataclass
import math

from ..models import Extent3D


@dataclass(frozen=True)
class RegularGrid3D:
    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]
    cell_size: tuple[float, float, float]
    shape_zyx: tuple[int, int, int]

    @classmethod
    def from_extent(cls, extent: Extent3D, tolerance: float = 1e-9) -> "RegularGrid3D":
        errors = extent.validate()
        if errors:
            raise ValueError(f"invalid extent: {errors}")
        counts = []
        for low, high, size in zip(extent.minimum, extent.maximum, extent.base_cell_size):
            ratio = (high - low) / size
            rounded = round(ratio)
            if rounded <= 0 or not math.isclose(ratio, rounded, rel_tol=0.0,
                                                abs_tol=tolerance * max(1.0, abs(ratio))):
                raise ValueError("extent lengths must be integer multiples of base cell size")
            counts.append(int(rounded))
        nx, ny, nz = counts
        return cls(extent.minimum, extent.maximum, extent.base_cell_size, (nz, ny, nx))

    @property
    def nx(self) -> int:
        return self.shape_zyx[2]

    @property
    def ny(self) -> int:
        return self.shape_zyx[1]

    @property
    def nz(self) -> int:
        return self.shape_zyx[0]

    @property
    def cell_volume(self) -> float:
        dx, dy, dz = self.cell_size
        return dx * dy * dz

    def x_center(self, index: int) -> float:
        return self._center(0, index, self.nx)

    def y_center(self, index: int) -> float:
        return self._center(1, index, self.ny)

    def z_center(self, index: int) -> float:
        return self._center(2, index, self.nz)

    def _center(self, axis: int, index: int, count: int) -> float:
        if not 0 <= index < count:
            raise IndexError("grid index outside extent")
        return self.minimum[axis] + (index + 0.5) * self.cell_size[axis]

    def to_dict(self) -> dict:
        return {"minimum": list(self.minimum), "maximum": list(self.maximum),
                "cellSize": list(self.cell_size), "shapeZYX": list(self.shape_zyx),
                "cellVolume": self.cell_volume, "gridType": "RegularCartesian"}

