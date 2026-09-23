"""Cross-cutting intrusion bodies as replacement volumes in deformed space."""

from __future__ import annotations

from dataclasses import dataclass
import math

from ..events.stratigraphic_events import voxelize_event_model
from ..physics.structural_3d import DeformedStructuralModel, transform_point


@dataclass(frozen=True)
class IntrusionOperation:
    event_id: str
    unit_id: str
    intrusion_style: str
    geometry_type: str
    host_unit_ids: tuple[str, ...]
    parameters: dict
    allow_domain_boundary_exit: bool
    evidence_source_ids: tuple[str, ...]


@dataclass(frozen=True)
class IntrusionModel:
    source_model: DeformedStructuralModel
    operations: tuple[IntrusionOperation, ...]
    labels_zyx: list
    validation: dict

    def to_dict(self):
        return {"sourceStructuralModel": self.source_model.to_dict(),
                "operations": [{"eventId": op.event_id, "unitId": op.unit_id,
                                "intrusionStyle": op.intrusion_style,
                                "geometryType": op.geometry_type,
                                "hostUnitIds": list(op.host_unit_ids),
                                "parameters": op.parameters,
                                "allowDomainBoundaryExit": op.allow_domain_boundary_exit,
                                "evidenceSourceIds": list(op.evidence_source_ids)}
                               for op in self.operations],
                "labelsZYX": self.labels_zyx, "validation": self.validation,
                "representation": "CrosscuttingReplacementVoxelModel"}


def apply_intrusions(structural_model: DeformedStructuralModel,
                     operations: tuple[IntrusionOperation, ...]) -> IntrusionModel:
    source = structural_model.source_model
    labels = voxelize_event_model(source)["labelsZYX"]
    labels = [[list(row) for row in layer] for layer in labels]
    errors, reports = [], []
    for operation in operations:
        replaced = {}; occupied = []
        for z in range(source.grid.nz):
            pz = source.grid.z_center(z)
            for y in range(source.grid.ny):
                py = source.grid.y_center(y)
                for x in range(source.grid.nx):
                    host = labels[z][y][x]
                    if host not in operation.host_unit_ids:
                        continue
                    point = (source.grid.x_center(x), py, pz)
                    deformed = transform_point(point, host, structural_model)
                    if point_inside_intrusion(deformed, operation):
                        replaced[host] = replaced.get(host, 0) + 1
                        labels[z][y][x] = operation.unit_id
                        occupied.append((x, y, z))
        report_errors = _validate_operation(operation, replaced, occupied, source.grid)
        errors.extend(report_errors)
        reports.append({"eventId": operation.event_id, "unitId": operation.unit_id,
                        "replacedHostCellCounts": replaced,
                        "crosscutHostCount": len(replaced),
                        "intrusionCellCount": len(occupied),
                        "touchesDomainBoundary": _touches_boundary(occupied, source.grid),
                        "passed": not report_errors, "errors": report_errors})
    counts = {}
    for layer in labels:
        for row in layer:
            for label in row:
                if label is not None:
                    counts[label] = counts.get(label, 0) + 1
    validation = {"passed": not errors, "gate": "IntrusionCrosscuttingPartition",
                  "errors": errors, "operationReports": reports,
                  "overlapCount": 0, "replacementSemantics": True,
                  "unitCellCounts": counts,
                  "unitVoxelizedVolumes": {key: value * source.grid.cell_volume
                                            for key, value in counts.items()}}
    return IntrusionModel(structural_model, operations, labels, validation)


def point_inside_intrusion(point, operation):
    p = operation.parameters
    if operation.geometry_type == "Ellipsoid":
        center, axes = p["center"], p["semiAxes"]
        return sum(((point[i] - center[i]) / axes[i]) ** 2 for i in range(3)) <= 1.0
    normal = p["planeNormal"]; norm = math.sqrt(sum(value * value for value in normal))
    distance = abs(sum(normal[i] * point[i] for i in range(3)) - p["planeOffset"]) / norm
    return distance <= p["halfThickness"]


def _validate_operation(operation, replaced, occupied, grid):
    errors = []
    if not occupied:
        errors.append({"code": "IntrusionDoesNotIntersectDeclaredHosts",
                       "eventId": operation.event_id})
    if operation.intrusion_style == "Dike" and len(replaced) < 2:
        errors.append({"code": "DikeDoesNotCrosscutMultipleHosts",
                       "eventId": operation.event_id})
    if operation.intrusion_style == "Sill" and operation.parameters.get(
            "relationshipEvidence") != "Concordant":
        errors.append({"code": "SillRequiresConcordanceEvidence",
                       "eventId": operation.event_id})
    if _touches_boundary(occupied, grid) and not operation.allow_domain_boundary_exit:
        errors.append({"code": "UnauthorizedDomainBoundaryExit",
                       "eventId": operation.event_id})
    return errors


def _touches_boundary(occupied, grid):
    return any(x in {0, grid.nx - 1} or y in {0, grid.ny - 1} or
               z in {0, grid.nz - 1} for x, y, z in occupied)
