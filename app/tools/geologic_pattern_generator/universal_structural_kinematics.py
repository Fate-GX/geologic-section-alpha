"""Evidence-gated structural kinematics shared by all regional generators."""

from __future__ import annotations

import math
from typing import Callable, Sequence

Point2 = tuple[float, float]


def determinant_2x2(matrix: Sequence[Sequence[float]]) -> float:
    if len(matrix) != 2 or any(len(row) != 2 for row in matrix):
        raise ValueError("matrix must be 2 by 2")
    return float(matrix[0][0]) * float(matrix[1][1]) - float(matrix[0][1]) * float(matrix[1][0])


def affine_map(points: Sequence[Point2], matrix: Sequence[Sequence[float]],
               translation: Point2 = (0.0, 0.0)) -> list[Point2]:
    """Apply one compatible affine map to every supplied material point."""
    if determinant_2x2(matrix) <= 0:
        raise ValueError("continuous deformation must preserve orientation and avoid collapse")
    a, b = (float(value) for value in matrix[0])
    c, d = (float(value) for value in matrix[1])
    tx, ty = map(float, translation)
    return [(a * float(x) + b * float(y) + tx,
             c * float(x) + d * float(y) + ty) for x, y in points]


def compact_support_attenuation(coordinate: float, half_extent: float) -> float:
    """Smooth finite support profile; coefficients remain evidence-conditioned."""
    half_extent = float(half_extent)
    if half_extent <= 0:
        raise ValueError("half_extent must be positive")
    ratio = abs(float(coordinate)) / half_extent
    return 0.0 if ratio >= 1.0 else (1.0 - ratio * ratio) ** 2


def fault_displacement(point: Point2, signed_fault_coordinate: float,
                       slip_vector: Point2, displacement: float,
                       extent_coordinate: float = 0.0,
                       half_extent: float | None = None,
                       partition: str = "positive-side") -> Point2:
    """Apply a piecewise fault displacement d*f1 with optional finite attenuation."""
    x, y = map(float, point)
    sx, sy = map(float, slip_vector)
    norm = math.hypot(sx, sy)
    if norm == 0:
        raise ValueError("slip_vector must be non-zero")
    sx, sy = sx / norm, sy / norm
    scale = float(displacement)
    if half_extent is not None:
        scale *= compact_support_attenuation(extent_coordinate, half_extent)
    if partition == "positive-side":
        side_scale = scale if signed_fault_coordinate >= 0 else 0.0
    elif partition == "symmetric":
        side_scale = 0.5 * scale if signed_fault_coordinate >= 0 else -0.5 * scale
    else:
        raise ValueError("partition must be positive-side or symmetric")
    return x + side_scale * sx, y + side_scale * sy


def apply_fault_operator(polylines: Sequence[Sequence[Point2]],
                         signed_coordinate: Callable[[Point2], float],
                         slip_vector: Point2, displacement: float,
                         extent_coordinate: Callable[[Point2], float] | None = None,
                         half_extent: float | None = None,
                         partition: str = "positive-side") -> list[list[Point2]]:
    """Apply the same fault operator to every affected geological boundary."""
    output = []
    for polyline in polylines:
        transformed = []
        for point in polyline:
            extent = extent_coordinate(point) if extent_coordinate else 0.0
            transformed.append(fault_displacement(
                point, signed_coordinate(point), slip_vector, displacement,
                extent, half_extent, partition))
        output.append(transformed)
    return output


def numerical_deformation_gradient(mapping: Callable[[Point2], Point2], point: Point2,
                                   step: float = 1e-5) -> list[list[float]]:
    """Central-difference deformation gradient for a continuous point map."""
    if step <= 0:
        raise ValueError("step must be positive")
    x, y = map(float, point)
    xp, xm = mapping((x + step, y)), mapping((x - step, y))
    yp, ym = mapping((x, y + step)), mapping((x, y - step))
    return [[(xp[0] - xm[0]) / (2 * step), (yp[0] - ym[0]) / (2 * step)],
            [(xp[1] - xm[1]) / (2 * step), (yp[1] - ym[1]) / (2 * step)]]


def validate_continuous_deformation(mapping: Callable[[Point2], Point2],
                                    sample_points: Sequence[Point2],
                                    minimum_jacobian: float = 1e-8) -> dict:
    """Reject local collapse or inversion; faults must be validated as discontinuities separately."""
    errors = []
    determinants = []
    for index, point in enumerate(sample_points):
        determinant = determinant_2x2(numerical_deformation_gradient(mapping, point))
        determinants.append(determinant)
        if determinant <= minimum_jacobian:
            errors.append({"code": "NonPositiveJacobian", "sampleIndex": index,
                           "determinant": determinant})
    return {"passed": not errors, "errors": errors, "jacobianDeterminants": determinants,
            "faultDiscontinuitiesExcluded": True}


def validate_structural_inputs(event: dict) -> dict:
    """Evidence gate for fold/fault generation, without inventing missing kinematics."""
    kind = event.get("eventType")
    missing = []
    if kind == "Fault":
        for key in ("faultSurface", "slipDirection", "displacementEvidence"):
            if not event.get(key):
                missing.append(key)
    elif kind == "Fold":
        for key in ("foldFrame", "orientationConstraints", "wavelengthOrHingeEvidence"):
            if not event.get(key):
                missing.append(key)
    else:
        missing.append("supportedEventType")
    return {"passed": not missing, "missingEvidence": missing,
            "geometryGenerationAuthorized": not missing}
