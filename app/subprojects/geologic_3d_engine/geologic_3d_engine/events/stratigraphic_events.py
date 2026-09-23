"""3D erosion, fill, onlap, pinch-out and lens operations on field-defined bodies."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from typing import Sequence

from ..geometry.regular_grid import RegularGrid3D
from ..stratigraphy.conformable_stack import (ConformableStack, Field2D,
                                               LayerVolume, _field)


def classify_interval_evidence(evidence: dict) -> dict:
    """Keep geological-event evidence separate from observation/data states."""
    if evidence.get("missingRecord"):
        return {"state": "MissingRecord", "category": "DataQualityState",
                "geologicalEvent": None}
    if evidence.get("nonpenetration"):
        return {"state": "Nonpenetration", "category": "EvidenceLimitState",
                "geologicalEvent": None}
    supported = []
    if any(evidence.get(key) for key in (
            "positiveTruncation", "erosionalSurface", "basalLag", "weatheringSurface")):
        supported.append("Erosion")
    if evidence.get("thicknessConvergesToZero"):
        supported.append("Pinchout")
    if evidence.get("elapsedTimeWithoutRemoval"):
        supported.append("Nondeposition")
    if len(supported) > 1:
        return {"state": "UnresolvedConflict", "category": "EvidenceConflict",
                "geologicalEvent": None, "supportedCandidates": supported}
    if len(supported) == 1:
        return {"state": "Supported", "category": "GeologicalInterpretation",
                "geologicalEvent": supported[0], "supportedCandidates": supported}
    return {"state": "Ambiguous", "category": "InsufficientEvidence",
            "geologicalEvent": None, "supportedCandidates": []}


@dataclass(frozen=True)
class EventVolumeModel:
    grid: RegularGrid3D
    primary_bodies: tuple[LayerVolume, ...]
    replacement_bodies: tuple[LayerVolume, ...] = ()
    erosion_surface: Field2D | None = None
    event_log: tuple[dict, ...] = ()

    def to_dict(self) -> dict:
        return {"grid": self.grid.to_dict(),
                "primaryBodies": [body.to_dict() for body in self.primary_bodies],
                "replacementBodies": [body.to_dict() for body in self.replacement_bodies],
                "erosionSurface": ([list(row) for row in self.erosion_surface]
                                   if self.erosion_surface else None),
                "eventLog": list(self.event_log)}


def from_conformable_stack(stack: ConformableStack) -> EventVolumeModel:
    return EventVolumeModel(stack.grid, stack.layers)


def apply_erosion(model: EventVolumeModel, erosion_surface: Sequence[Sequence[float]],
                  event_id: str, tolerance: float = 1e-9) -> EventVolumeModel:
    """Remove only pre-existing material above the event surface."""
    surface = _field(erosion_surface, model.grid.ny, model.grid.nx, "erosionSurface")
    bodies = []
    removed_volume = 0.0
    area = model.grid.cell_size[0] * model.grid.cell_size[1]
    for body in model.primary_bodies:
        top_rows, active_rows, removed_rows = [], [], []
        for y in range(model.grid.ny):
            top_row, active_row, removed_row = [], [], []
            for x in range(model.grid.nx):
                old_top, bottom, erosion = body.top[y][x], body.bottom[y][x], surface[y][x]
                retained = max(0.0, min(old_top, erosion) - bottom)
                removed = max(0.0, old_top - bottom) - retained
                top_row.append(bottom + retained)
                active_row.append(retained > tolerance)
                removed_row.append(removed)
                removed_volume += removed * area
            top_rows.append(tuple(top_row)); active_rows.append(tuple(active_row)); removed_rows.append(tuple(removed_row))
        top = tuple(top_rows)
        thickness = tuple(tuple(top[y][x] - body.bottom[y][x] for x in range(model.grid.nx))
                          for y in range(model.grid.ny))
        bodies.append(LayerVolume(body.unit_id, body.order_index, top, body.bottom,
                                  thickness, tuple(active_rows)))
    effective_surface = tuple(tuple(
        max((body.top[y][x] for body in bodies if body.active[y][x]),
            default=surface[y][x])
        for x in range(model.grid.nx)) for y in range(model.grid.ny))
    event = {"eventId": event_id, "eventType": "Erosion",
             "removedGeometricVolume": removed_volume,
             "oldMaterialMayCrossSurface": False,
             "effectiveSurfaceUsesRetainedTop": True}
    return EventVolumeModel(model.grid, tuple(bodies), model.replacement_bodies,
                            effective_surface, model.event_log + (event,))


def build_deposit_on_surface(model: EventVolumeModel, unit_id: str,
                             thickness_field: Sequence[Sequence[float]], event_id: str,
                             mode: str, tolerance: float = 1e-9) -> EventVolumeModel:
    """Add younger fill/onlap without independently perturbing its basal contact."""
    if mode not in {"ErosionFill", "Onlap"}:
        raise ValueError("mode must be ErosionFill or Onlap")
    thickness = _field(thickness_field, model.grid.ny, model.grid.nx, "depositThickness")
    if any(value < 0 for row in thickness for value in row):
        raise ValueError("deposit thickness must be non-negative")
    if mode == "ErosionFill":
        if model.erosion_surface is None:
            raise ValueError("ErosionFill requires a preceding erosion surface")
        bottom = model.erosion_surface
    else:
        bottom = tuple(tuple(max((body.top[y][x] for body in model.primary_bodies
                                  if body.active[y][x]), default=model.grid.minimum[2])
                             for x in range(model.grid.nx)) for y in range(model.grid.ny))
    top = tuple(tuple(bottom[y][x] + thickness[y][x] for x in range(model.grid.nx))
                for y in range(model.grid.ny))
    active = tuple(tuple(thickness[y][x] > tolerance for x in range(model.grid.nx))
                   for y in range(model.grid.ny))
    body = LayerVolume(unit_id, -1, top, bottom, thickness, active)
    if any(top[y][x] > model.grid.maximum[2] + tolerance
           for y in range(model.grid.ny) for x in range(model.grid.nx)):
        raise ValueError("deposit exceeds vertical model extent")
    pinchout_faces = _active_transition_count(active)
    event = {"eventId": event_id, "eventType": mode, "unitId": unit_id,
             "pinchoutFaceCount": pinchout_faces,
             "erodesOlderMaterial": False if mode == "Onlap" else None}
    return EventVolumeModel(model.grid, (body,) + model.primary_bodies,
                            model.replacement_bodies, model.erosion_surface,
                            model.event_log + (event,))


def build_stratified_erosion_fill(
        model: EventVolumeModel,
        subunits: Sequence[tuple[str, Sequence[Sequence[float]], str]],
        *, accommodation_ceiling: Sequence[Sequence[float]] | None = None,
        tolerance: float = 1e-9) -> EventVolumeModel:
    """Stack ordered valley-fill subunits without reusing the erosion base.

    ``subunits`` contains ``(unit_id, thickness_field, event_id)`` records in
    depositional order.  The first bottom is the effective erosion surface;
    every later bottom is the exact preceding top.  The optional ceiling clips
    positive thickness to the declared accommodation space, allowing marginal
    pinch-out without overlap.
    """
    if model.erosion_surface is None:
        raise ValueError("StratifiedErosionFill requires a preceding erosion surface")
    if not subunits:
        raise ValueError("StratifiedErosionFill requires at least one subunit")
    ids = [record[0] for record in subunits]
    events = [record[2] for record in subunits]
    if len(set(ids)) != len(ids) or len(set(events)) != len(events):
        raise ValueError("stratified fill unit and event IDs must be unique")

    ceiling = (_field(accommodation_ceiling, model.grid.ny, model.grid.nx,
                      "accommodationCeiling")
               if accommodation_ceiling is not None else
               tuple(tuple(model.grid.maximum[2] for _ in range(model.grid.nx))
                     for _ in range(model.grid.ny)))
    bottom = model.erosion_surface
    added, event_log = [], list(model.event_log)
    for index, (unit_id, thickness_field, event_id) in enumerate(subunits):
        requested = _field(thickness_field, model.grid.ny, model.grid.nx,
                           "depositThickness")
        if any(value < 0 for row in requested for value in row):
            raise ValueError("deposit thickness must be non-negative")
        top = tuple(tuple(min(bottom[y][x] + requested[y][x], ceiling[y][x])
                          for x in range(model.grid.nx))
                    for y in range(model.grid.ny))
        if any(ceiling[y][x] < bottom[y][x] - tolerance
               for y in range(model.grid.ny) for x in range(model.grid.nx)):
            raise ValueError("accommodation ceiling lies below accumulated fill")
        thickness = tuple(tuple(max(0.0, top[y][x] - bottom[y][x])
                                for x in range(model.grid.nx))
                          for y in range(model.grid.ny))
        active = tuple(tuple(thickness[y][x] > tolerance
                             for x in range(model.grid.nx))
                       for y in range(model.grid.ny))
        added.append(LayerVolume(unit_id, -1-index, top, bottom, thickness, active))
        event_log.append({"eventId": event_id,
                          "eventType": "StratifiedErosionFill",
                          "unitId": unit_id,
                          "subunitIndex": index,
                          "bottomPolicy": ("ErosionSurface" if index == 0
                                           else "ExactPredecessorTop"),
                          "pinchoutFaceCount": _active_transition_count(active),
                          "erodesOlderMaterial": False})
        bottom = top
    # Youngest body first, consistent with build_deposit_on_surface.
    return EventVolumeModel(model.grid, tuple(reversed(added)) + model.primary_bodies,
                            model.replacement_bodies, model.erosion_surface,
                            tuple(event_log))


def _active_transition_count(active) -> int:
    ny, nx = len(active), len(active[0])
    count = 0
    for y in range(ny):
        for x in range(nx):
            if x + 1 < nx and active[y][x] != active[y][x + 1]:
                count += 1
            if y + 1 < ny and active[y][x] != active[y + 1][x]:
                count += 1
    return count


def _component_count(active) -> int:
    ny, nx = len(active), len(active[0])
    seen, components = set(), 0
    for start_y in range(ny):
        for start_x in range(nx):
            if not active[start_y][start_x] or (start_y, start_x) in seen:
                continue
            components += 1
            queue = deque([(start_y, start_x)]); seen.add((start_y, start_x))
            while queue:
                y, x = queue.popleft()
                for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= yy < ny and 0 <= xx < nx and active[yy][xx] and (yy, xx) not in seen:
                        seen.add((yy, xx)); queue.append((yy, xx))
    return components


def build_lens_in_host(model: EventVolumeModel, host_unit_id: str, lens_unit_id: str,
                       bottom_surface: Sequence[Sequence[float]],
                       thickness_field: Sequence[Sequence[float]], event_id: str,
                       allow_domain_boundary_exit: bool = False,
                       tolerance: float = 1e-9) -> EventVolumeModel:
    hosts = [body for body in model.primary_bodies if body.unit_id == host_unit_id]
    if len(hosts) != 1:
        raise ValueError("lens host must resolve to exactly one primary body")
    host = hosts[0]
    bottom = _field(bottom_surface, model.grid.ny, model.grid.nx, "lensBottom")
    thickness = _field(thickness_field, model.grid.ny, model.grid.nx, "lensThickness")
    if any(value < 0 for row in thickness for value in row):
        raise ValueError("lens thickness must be non-negative")
    top = tuple(tuple(bottom[y][x] + thickness[y][x] for x in range(model.grid.nx))
                for y in range(model.grid.ny))
    active = tuple(tuple(thickness[y][x] > tolerance for x in range(model.grid.nx))
                   for y in range(model.grid.ny))
    for y in range(model.grid.ny):
        for x in range(model.grid.nx):
            if active[y][x] and (bottom[y][x] < host.bottom[y][x] - tolerance or
                                 top[y][x] > host.top[y][x] + tolerance):
                raise ValueError("lens is not contained in its host body")
    if not allow_domain_boundary_exit:
        border = ([active[0][x] for x in range(model.grid.nx)] +
                  [active[-1][x] for x in range(model.grid.nx)] +
                  [active[y][0] for y in range(model.grid.ny)] +
                  [active[y][-1] for y in range(model.grid.ny)])
        if any(border):
            raise ValueError("internal lens must close before the XY model boundary")
    lens = LayerVolume(lens_unit_id, -1, top, bottom, thickness, active)
    event = {"eventId": event_id, "eventType": "LensReplacement",
             "unitId": lens_unit_id, "hostUnitId": host_unit_id,
             "connectedComponentCount": _component_count(active),
             "pinchoutFaceCount": _active_transition_count(active),
             "replacementSemantics": True}
    return EventVolumeModel(model.grid, model.primary_bodies,
                            model.replacement_bodies + (lens,), model.erosion_surface,
                            model.event_log + (event,))


def voxelize_event_model(model: EventVolumeModel) -> dict:
    labels = [[[None for _ in range(model.grid.nx)] for _ in range(model.grid.ny)]
              for _ in range(model.grid.nz)]
    overlaps, replacement_errors = [], []
    counts = {body.unit_id: 0 for body in model.primary_bodies + model.replacement_bodies}
    for z_index in range(model.grid.nz):
        z = model.grid.z_center(z_index)
        for y in range(model.grid.ny):
            for x in range(model.grid.nx):
                primary = [body.unit_id for body in model.primary_bodies
                           if body.active[y][x] and body.bottom[y][x] < z <= body.top[y][x]]
                replacements = [body for body in model.replacement_bodies
                                if body.active[y][x] and body.bottom[y][x] < z <= body.top[y][x]]
                if len(primary) > 1 or len(replacements) > 1:
                    overlaps.append({"xIndex": x, "yIndex": y, "zIndex": z_index,
                                     "primary": primary,
                                     "replacements": [body.unit_id for body in replacements]})
                    continue
                if replacements:
                    replacement = replacements[0]
                    event = next(item for item in model.event_log
                                 if item.get("unitId") == replacement.unit_id and
                                 item.get("eventType") == "LensReplacement")
                    if primary != [event["hostUnitId"]]:
                        replacement_errors.append({"code": "LensVoxelOutsideHost",
                                                   "unitId": replacement.unit_id,
                                                   "xIndex": x, "yIndex": y,
                                                   "zIndex": z_index})
                        continue
                    label = replacement.unit_id
                else:
                    label = primary[0] if primary else None
                labels[z_index][y][x] = label
                if label is not None:
                    counts[label] += 1
    return {"passed": not overlaps and not replacement_errors, "gate": "EventBodyPartition",
            "labelsZYX": labels, "unitCellCounts": counts,
            "unitVoxelizedVolumes": {key: value * model.grid.cell_volume
                                     for key, value in counts.items()},
            "overlapCount": len(overlaps), "overlaps": overlaps,
            "replacementErrorCount": len(replacement_errors),
            "replacementErrors": replacement_errors}
