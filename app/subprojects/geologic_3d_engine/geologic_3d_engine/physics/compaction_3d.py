"""Solid-preserving vertical compaction of Stage-3 event volumes."""

from __future__ import annotations

from dataclasses import dataclass

from ..events.stratigraphic_events import EventVolumeModel, voxelize_event_model
from ..stratigraphy.conformable_stack import LayerVolume, _field
from .compaction import transform_thickness


@dataclass(frozen=True)
class UnitPorosityState:
    unit_id: str
    source_porosity: tuple
    target_porosity: tuple
    evidence_source_ids: tuple[str, ...]


def compact_event_model(model: EventVolumeModel, states: tuple[UnitPorosityState, ...],
                        event_id: str, tolerance: float = 1e-9) -> tuple[EventVolumeModel, dict]:
    """Compact top-down with a fixed top and exact shared active contacts."""
    state_map = {state.unit_id: state for state in states}
    bodies = model.primary_bodies + model.replacement_bodies
    if len(state_map) != len(states) or set(state_map) != {body.unit_id for body in bodies}:
        raise ValueError("porosity states must cover every primary and replacement unit exactly")
    area = model.grid.cell_size[0] * model.grid.cell_size[1]
    current_top = [[max((body.top[y][x] for body in model.primary_bodies if body.active[y][x]),
                       default=model.grid.minimum[2])
                    for x in range(model.grid.nx)] for y in range(model.grid.ny)]
    compacted, ratios, conservation = [], {}, []
    for body in model.primary_bodies:
        state = state_map[body.unit_id]
        top_rows, bottom_rows, thick_rows, active_rows, ratio_rows = [], [], [], [], []
        source_solid = target_solid = 0.0
        for y in range(model.grid.ny):
            tr, br, hr, ar, rr = [], [], [], [], []
            for x in range(model.grid.nx):
                old = body.thickness[y][x] if body.active[y][x] else 0.0
                result = transform_thickness(old, state.source_porosity[y][x],
                                             state.target_porosity[y][x])
                if result["targetThickness"] > old + tolerance:
                    raise ValueError(f"target porosity causes decompaction for {body.unit_id}")
                new = result["targetThickness"]
                top = current_top[y][x]; bottom = top - new
                if bottom < model.grid.minimum[2] - tolerance:
                    raise ValueError("compacted stack exceeds lower vertical extent")
                tr.append(top); br.append(bottom); hr.append(new); ar.append(new > tolerance)
                rr.append(new / old if old > tolerance else 1.0)
                current_top[y][x] = bottom
                source_solid += result["solidThickness"] * area
                target_solid += new * (1.0 - state.target_porosity[y][x]) * area
            top_rows.append(tuple(tr)); bottom_rows.append(tuple(br)); thick_rows.append(tuple(hr))
            active_rows.append(tuple(ar)); ratio_rows.append(tuple(rr))
        compacted.append(LayerVolume(body.unit_id, body.order_index, tuple(top_rows),
                                     tuple(bottom_rows), tuple(thick_rows), tuple(active_rows)))
        ratios[body.unit_id] = tuple(ratio_rows)
        conservation.append(_conservation(body.unit_id, source_solid, target_solid, tolerance))

    replacement = []
    for lens in model.replacement_bodies:
        event = next(item for item in model.event_log
                     if item.get("eventType") == "LensReplacement" and
                     item.get("unitId") == lens.unit_id)
        old_host = next(body for body in model.primary_bodies
                        if body.unit_id == event["hostUnitId"])
        new_host = next(body for body in compacted if body.unit_id == event["hostUnitId"])
        state, host_ratios = state_map[lens.unit_id], ratios[event["hostUnitId"]]
        top_rows, bottom_rows, thick_rows, active_rows = [], [], [], []
        source_solid = target_solid = 0.0
        for y in range(model.grid.ny):
            tr, br, hr, ar = [], [], [], []
            for x in range(model.grid.nx):
                old = lens.thickness[y][x] if lens.active[y][x] else 0.0
                result = transform_thickness(old, state.source_porosity[y][x],
                                             state.target_porosity[y][x])
                ratio = result["targetThickness"] / old if old > tolerance else 1.0
                if lens.active[y][x] and abs(ratio - host_ratios[y][x]) > tolerance:
                    raise ValueError("differential lens/host compaction requires a coupled solver")
                bottom = new_host.bottom[y][x] + (lens.bottom[y][x] - old_host.bottom[y][x]) * host_ratios[y][x]
                top = bottom + result["targetThickness"]
                tr.append(top); br.append(bottom); hr.append(result["targetThickness"])
                ar.append(result["targetThickness"] > tolerance)
                source_solid += result["solidThickness"] * area
                target_solid += result["targetThickness"] * (1.0 - state.target_porosity[y][x]) * area
            top_rows.append(tuple(tr)); bottom_rows.append(tuple(br)); thick_rows.append(tuple(hr)); active_rows.append(tuple(ar))
        replacement.append(LayerVolume(lens.unit_id, lens.order_index, tuple(top_rows),
                                       tuple(bottom_rows), tuple(thick_rows), tuple(active_rows)))
        conservation.append(_conservation(lens.unit_id, source_solid, target_solid, tolerance))

    erosion = _map_surface(model, tuple(compacted), model.erosion_surface, tolerance)
    event = {"eventId": event_id, "eventType": "Compaction",
             "anchor": "TopSurfaceFixed", "solidVolumePreserved": all(
                 item["passed"] for item in conservation),
             "lithologyNameAloneUsed": False}
    result_model = EventVolumeModel(model.grid, tuple(compacted), tuple(replacement), erosion,
                                    model.event_log + (event,))
    partition = voxelize_event_model(result_model)
    gate = {"passed": all(item["passed"] for item in conservation) and partition["passed"],
            "gate": "SolidVolumeAndCompactedPartition", "unitConservation": conservation,
            "partition": {key: value for key, value in partition.items() if key != "labelsZYX"},
            "anchor": "TopSurfaceFixed"}
    return result_model, gate


def _conservation(unit_id, source, target, tolerance):
    error = target - source
    allowed = tolerance * max(1.0, abs(source))
    return {"unitId": unit_id, "sourceSolidVolume": source,
            "targetSolidVolume": target, "absoluteError": error,
            "passed": abs(error) <= allowed}


def _map_surface(old_model, new_bodies, surface, tolerance):
    if surface is None:
        return None
    rows = []
    for y in range(old_model.grid.ny):
        row = []
        for x in range(old_model.grid.nx):
            value = surface[y][x]; mapped = value
            for old, new in zip(old_model.primary_bodies, new_bodies):
                if abs(value - old.top[y][x]) <= tolerance:
                    mapped = new.top[y][x]; break
                if abs(value - old.bottom[y][x]) <= tolerance:
                    mapped = new.bottom[y][x]; break
                if old.bottom[y][x] < value < old.top[y][x] and old.thickness[y][x] > tolerance:
                    fraction = (value - old.bottom[y][x]) / old.thickness[y][x]
                    mapped = new.bottom[y][x] + fraction * new.thickness[y][x]; break
            row.append(mapped)
        rows.append(tuple(row))
    return tuple(rows)
