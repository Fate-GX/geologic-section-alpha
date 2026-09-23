"""Positive-thickness 3D conformable stacks with exact shared contacts."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from ..geometry.regular_grid import RegularGrid3D

Field2D = tuple[tuple[float, ...], ...]


def _field(values: Sequence[Sequence[float]], ny: int, nx: int, name: str) -> Field2D:
    if len(values) != ny or any(len(row) != nx for row in values):
        raise ValueError(f"{name} shape must be [ny={ny}][nx={nx}]")
    result = tuple(tuple(float(value) for value in row) for row in values)
    if any(not math.isfinite(value) for row in result for value in row):
        raise ValueError(f"{name} contains a non-finite value")
    return result


@dataclass(frozen=True)
class LayerVolume:
    unit_id: str
    order_index: int
    top: Field2D
    bottom: Field2D
    thickness: Field2D
    active: tuple[tuple[bool, ...], ...]

    def to_dict(self) -> dict:
        return {"unitId": self.unit_id, "orderIndex": self.order_index,
                "top": [list(row) for row in self.top],
                "bottom": [list(row) for row in self.bottom],
                "thickness": [list(row) for row in self.thickness],
                "active": [list(row) for row in self.active]}


@dataclass(frozen=True)
class ConformableStack:
    grid: RegularGrid3D
    layers: tuple[LayerVolume, ...]
    zero_thickness_tolerance: float

    def validate(self, tolerance: float = 1e-9) -> dict:
        errors = []
        for layer_index, layer in enumerate(self.layers):
            for y in range(self.grid.ny):
                for x in range(self.grid.nx):
                    top = layer.top[y][x]
                    bottom = layer.bottom[y][x]
                    thickness = layer.thickness[y][x]
                    if thickness < -tolerance or bottom > top + tolerance:
                        errors.append({"code": "NegativeThickness", "unitId": layer.unit_id,
                                       "xIndex": x, "yIndex": y})
                    if not math.isclose(top - bottom, thickness, rel_tol=0.0,
                                        abs_tol=tolerance):
                        errors.append({"code": "ThicknessIdentityFailure", "unitId": layer.unit_id,
                                       "xIndex": x, "yIndex": y})
                    expected_active = thickness > self.zero_thickness_tolerance
                    if layer.active[y][x] != expected_active:
                        errors.append({"code": "ActiveMaskMismatch", "unitId": layer.unit_id,
                                       "xIndex": x, "yIndex": y})
                    if top > self.grid.maximum[2] + tolerance or bottom < self.grid.minimum[2] - tolerance:
                        errors.append({"code": "LayerOutsideVerticalExtent", "unitId": layer.unit_id,
                                       "xIndex": x, "yIndex": y})
            if layer_index:
                upper = self.layers[layer_index - 1]
                for y in range(self.grid.ny):
                    for x in range(self.grid.nx):
                        if not math.isclose(upper.bottom[y][x], layer.top[y][x],
                                            rel_tol=0.0, abs_tol=tolerance):
                            errors.append({"code": "UnsharedContact", "upperUnitId": upper.unit_id,
                                           "lowerUnitId": layer.unit_id,
                                           "xIndex": x, "yIndex": y})
        return {"passed": not errors, "errors": errors,
                "gate": "PositiveThicknessAndSharedContacts",
                "layerCount": len(self.layers),
                "independentContactGenerationAllowed": False}

    def to_dict(self) -> dict:
        return {"grid": self.grid.to_dict(), "layers": [layer.to_dict() for layer in self.layers],
                "zeroThicknessTolerance": self.zero_thickness_tolerance,
                "construction": "SequentialSharedContacts"}


def build_conformable_stack(grid: RegularGrid3D, top_surface: Sequence[Sequence[float]],
                            unit_ids: Sequence[str],
                            thickness_fields: Sequence[Sequence[Sequence[float]]],
                            zero_thickness_tolerance: float = 1e-9) -> ConformableStack:
    if not unit_ids or len(unit_ids) != len(thickness_fields):
        raise ValueError("unit_ids and thickness_fields must be non-empty and have equal length")
    if len(set(unit_ids)) != len(unit_ids):
        raise ValueError("unit_ids contain duplicates")
    if zero_thickness_tolerance < 0:
        raise ValueError("zero_thickness_tolerance must be non-negative")
    current_top = _field(top_surface, grid.ny, grid.nx, "top_surface")
    layers = []
    for order_index, (unit_id, raw_thickness) in enumerate(zip(unit_ids, thickness_fields)):
        thickness = _field(raw_thickness, grid.ny, grid.nx, f"thickness[{unit_id}]")
        if any(value < 0 for row in thickness for value in row):
            raise ValueError(f"negative thickness in unit {unit_id}")
        bottom = tuple(tuple(current_top[y][x] - thickness[y][x]
                             for x in range(grid.nx)) for y in range(grid.ny))
        active = tuple(tuple(thickness[y][x] > zero_thickness_tolerance
                             for x in range(grid.nx)) for y in range(grid.ny))
        layers.append(LayerVolume(str(unit_id), order_index, current_top, bottom, thickness, active))
        current_top = bottom
    stack = ConformableStack(grid, tuple(layers), zero_thickness_tolerance)
    report = stack.validate()
    if not report["passed"]:
        raise ValueError(f"invalid conformable stack: {report['errors']}")
    return stack


def voxelize_stack(stack: ConformableStack) -> dict:
    """Assign each regular-grid cell center to at most one unit using half-open layers."""
    labels = [[[None for _ in range(stack.grid.nx)] for _ in range(stack.grid.ny)]
              for _ in range(stack.grid.nz)]
    overlaps = []
    counts = {layer.unit_id: 0 for layer in stack.layers}
    envelope_voids = []
    for z_index in range(stack.grid.nz):
        z = stack.grid.z_center(z_index)
        for y in range(stack.grid.ny):
            for x in range(stack.grid.nx):
                matches = [layer.unit_id for layer in stack.layers
                           if layer.active[y][x] and layer.bottom[y][x] < z <= layer.top[y][x]]
                if len(matches) > 1:
                    overlaps.append({"xIndex": x, "yIndex": y, "zIndex": z_index,
                                     "unitIds": matches})
                elif matches:
                    labels[z_index][y][x] = matches[0]
                    counts[matches[0]] += 1
                envelope_top = stack.layers[0].top[y][x]
                envelope_bottom = stack.layers[-1].bottom[y][x]
                if envelope_bottom < z <= envelope_top and not matches:
                    envelope_voids.append({"xIndex": x, "yIndex": y, "zIndex": z_index})
    voxelized_volumes = {unit_id: count * stack.grid.cell_volume
                         for unit_id, count in counts.items()}
    column_area = stack.grid.cell_size[0] * stack.grid.cell_size[1]
    geometric_volumes = {
        layer.unit_id: sum(value for row in layer.thickness for value in row) * column_area
        for layer in stack.layers}
    return {"labelsZYX": labels, "unitCellCounts": counts,
            "unitGeometricVolumes": geometric_volumes,
            "unitVoxelizedVolumes": voxelized_volumes,
            "volumeDiscretizationError": {
                unit_id: voxelized_volumes[unit_id] - geometric_volumes[unit_id]
                for unit_id in counts},
            "overlapCount": len(overlaps), "overlaps": overlaps,
            "envelopeVoidCount": len(envelope_voids), "envelopeVoids": envelope_voids,
            "passed": not overlaps and not envelope_voids,
            "gate": "VoxelPartitionCompleteness"}
