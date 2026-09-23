"""Evidence-explicit continuous fold fields and piecewise 3D fault displacement."""

from __future__ import annotations

from dataclasses import dataclass
import math

from ..events.stratigraphic_events import EventVolumeModel

Point3 = tuple[float, float, float]


@dataclass(frozen=True)
class StructuralOperation:
    event_id: str
    operation: str
    affected_unit_ids: tuple[str, ...]
    parameters: dict


@dataclass(frozen=True)
class DeformedStructuralModel:
    source_model: EventVolumeModel
    operations: tuple[StructuralOperation, ...]
    samples_by_unit: dict
    validation: dict

    def to_dict(self):
        return {"sourceModel": self.source_model.to_dict(),
                "operations": [{"eventId": item.event_id, "operation": item.operation,
                                "affectedUnitIds": list(item.affected_unit_ids),
                                "parameters": item.parameters} for item in self.operations],
                "samplesByUnit": self.samples_by_unit, "validation": self.validation,
                "representation": "DeformedMaterialPointLattice"}


def deform_model(model: EventVolumeModel, operations: tuple[StructuralOperation, ...],
                 tolerance: float = 1e-9) -> DeformedStructuralModel:
    body_ids = {body.unit_id for body in model.primary_bodies + model.replacement_bodies}
    errors, gates = [], []
    for operation in operations:
        unknown = set(operation.affected_unit_ids) - body_ids
        if unknown:
            errors.append({"code": "UnknownAffectedUnit", "unitIds": sorted(unknown)})
        if operation.operation == "FoldDisplacementField":
            values = operation.parameters["verticalDisplacement"]
            if len(values) != model.grid.ny or any(len(row) != model.grid.nx for row in values):
                errors.append({"code": "FoldFieldShapeMismatch", "eventId": operation.event_id})
            gate = _fold_jacobian_gate(operation, model)
            gates.append(gate); errors.extend(gate["errors"])
        elif operation.operation == "PlanarFaultSlip":
            gate = _fault_gate(operation)
            gates.append(gate); errors.extend(gate["errors"])
        else:
            errors.append({"code": "UnsupportedStructuralOperation",
                           "operation": operation.operation})
    if errors:
        return DeformedStructuralModel(model, operations, {},
            {"passed": False, "gate": "StructuralKinematics", "errors": errors,
             "operationGates": gates})

    samples = {}
    for body in model.primary_bodies + model.replacement_bodies:
        records = []
        for y in range(model.grid.ny):
            for x in range(model.grid.nx):
                if not body.active[y][x]:
                    continue
                cx = model.grid.minimum[0] + (x + .5) * model.grid.cell_size[0]
                cy = model.grid.minimum[1] + (y + .5) * model.grid.cell_size[1]
                for boundary, z in (("Top", body.top[y][x]), ("Bottom", body.bottom[y][x])):
                    source = (cx, cy, z); target = source
                    applied = []
                    for operation in operations:
                        if body.unit_id in operation.affected_unit_ids:
                            target = _apply(target, operation, model, x, y)
                            applied.append(operation.event_id)
                    records.append({"xIndex": x, "yIndex": y, "boundary": boundary,
                                    "source": list(source), "target": list(target),
                                    "appliedEventIds": applied})
        samples[body.unit_id] = records
    validation = {"passed": True, "gate": "StructuralKinematics", "errors": [],
                  "operationGates": gates, "allAffectedSamplesUseSameOperator": True,
                  "faultsRemainTypedDiscontinuities": True,
                  "sampleCount": sum(len(value) for value in samples.values())}
    return DeformedStructuralModel(model, operations, samples, validation)


def _fold_jacobian_gate(operation, model):
    values = operation.parameters["verticalDisplacement"]
    finite = all(math.isfinite(float(value)) for row in values for value in row)
    determinants = [1.0 for _ in range(model.grid.nx * model.grid.ny)] if finite else []
    errors = [] if finite else [{"code": "NonFiniteFoldDisplacement",
                                 "eventId": operation.event_id}]
    return {"passed": not errors, "gate": "PositiveFoldJacobian",
            "eventId": operation.event_id, "minimumJacobian": min(determinants) if determinants else None,
            "jacobianDeterminants": determinants, "errors": errors,
            "mappingClass": "ContinuousBilinearVerticalShear_XYFixed"}


def _fault_gate(operation):
    p = operation.parameters
    normal, slip, displacement = p["planeNormal"], p["slipVector"], float(p["displacement"])
    errors = []
    if len(normal) != 3 or math.sqrt(sum(float(v) ** 2 for v in normal)) <= 0:
        errors.append({"code": "InvalidFaultPlane", "eventId": operation.event_id})
    if len(slip) != 3 or math.sqrt(sum(float(v) ** 2 for v in slip)) <= 0:
        errors.append({"code": "InvalidSlipVector", "eventId": operation.event_id})
    if not math.isfinite(displacement):
        errors.append({"code": "InvalidDisplacement", "eventId": operation.event_id})
    if p.get("partition", "positive-side") not in {"positive-side", "symmetric"}:
        errors.append({"code": "InvalidFaultPartition", "eventId": operation.event_id})
    return {"passed": not errors, "gate": "FaultOperatorConsistency",
            "eventId": operation.event_id, "errors": errors,
            "sameOperatorForAllAffectedUnits": not errors}


def _apply(point: Point3, operation: StructuralOperation, model, x_index, y_index) -> Point3:
    x, y, z = point; p = operation.parameters
    if operation.operation == "FoldDisplacementField":
        return x, y, z + fold_displacement_at(x, y, p["verticalDisplacement"], model.grid)
    normal = [float(v) for v in p["planeNormal"]]
    slip = [float(v) for v in p["slipVector"]]
    offset = float(p["planeOffset"]); displacement = float(p["displacement"])
    signed = normal[0] * x + normal[1] * y + normal[2] * z - offset
    norm = math.sqrt(sum(value * value for value in slip)); slip = [value / norm for value in slip]
    if p.get("partition", "positive-side") == "symmetric":
        scale = .5 * displacement if signed >= 0 else -.5 * displacement
    else:
        scale = displacement if signed >= 0 else 0.0
    return tuple(point[i] + scale * slip[i] for i in range(3))


def transform_point(point: Point3, unit_id: str, model: DeformedStructuralModel) -> Point3:
    """Replay the validated structural event chain for an arbitrary material point."""
    target = tuple(map(float, point))
    grid = model.source_model.grid
    x_index = max(0, min(grid.nx - 1,
                         int((target[0] - grid.minimum[0]) / grid.cell_size[0])))
    y_index = max(0, min(grid.ny - 1,
                         int((target[1] - grid.minimum[1]) / grid.cell_size[1])))
    for operation in model.operations:
        if unit_id in operation.affected_unit_ids:
            target = _apply(target, operation, model.source_model, x_index, y_index)
    return target


def fold_displacement_at(x, y, values, grid):
    """Continuous bilinear interpolation of a field sampled at XY cell centres."""
    gx = (float(x) - grid.minimum[0]) / grid.cell_size[0] - .5
    gy = (float(y) - grid.minimum[1]) / grid.cell_size[1] - .5
    x0 = max(0, min(grid.nx - 1, math.floor(gx))); x1 = max(0, min(grid.nx - 1, x0 + 1))
    y0 = max(0, min(grid.ny - 1, math.floor(gy))); y1 = max(0, min(grid.ny - 1, y0 + 1))
    tx = max(0.0, min(1.0, gx - x0)); ty = max(0.0, min(1.0, gy - y0))
    a = float(values[y0][x0]) * (1 - tx) + float(values[y0][x1]) * tx
    b = float(values[y1][x0]) * (1 - tx) + float(values[y1][x1]) * tx
    return a * (1 - ty) + b * ty
