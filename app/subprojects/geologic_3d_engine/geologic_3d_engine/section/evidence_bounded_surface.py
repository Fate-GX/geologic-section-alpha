"""Evidence-gated structural surface with a no-extrapolation convex hull."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np

from .rbf_structural_surface import RbfStructuralSurface


def _cross(origin, a, b):
    return ((a[0] - origin[0]) * (b[1] - origin[1])
            - (a[1] - origin[1]) * (b[0] - origin[0]))


def _convex_hull(points):
    ordered = sorted(set((float(x), float(y)) for x, y in points))
    if len(ordered) < 3:
        return []
    lower = []
    for point in ordered:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(ordered):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _inside_convex_polygon(point, polygon, tolerance):
    signs = []
    for i, start in enumerate(polygon):
        value = _cross(start, polygon[(i + 1) % len(polygon)], point)
        if abs(value) > tolerance:
            signs.append(value > 0)
    return not signs or all(sign == signs[0] for sign in signs)


def audit_surface_controls(controls: Sequence[Mapping]) -> dict:
    """Require compatible, observed, absolute-Z controls spanning an XY area."""
    if not isinstance(controls, Sequence) or isinstance(controls, (str, bytes)):
        raise ValueError("controls must be a sequence")
    errors = []
    xyz = []
    contact_ids = set()
    support_ids = set()
    for index, item in enumerate(controls):
        if not isinstance(item, Mapping):
            raise ValueError("every control must be a mapping")
        try:
            row = [float(item[key]) for key in ("xM", "yM", "zM")]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("every control requires numeric xM, yM and zM") from exc
        if not all(math.isfinite(value) for value in row):
            raise ValueError("control coordinates must be finite")
        xyz.append(row)
        contact_ids.add(item.get("contactId"))
        support_id = item.get("independentSupportId")
        if not isinstance(support_id, str) or not support_id.strip():
            errors.append({"code": "IndependentSupportIdentityMissing", "index": index})
        else:
            support_ids.add(support_id)
        if item.get("constraintRole") != "DirectSubsurfaceContact":
            errors.append({"code": "NotDirectSubsurfaceContact", "index": index})
        if item.get("evidenceStatus") != "Observed":
            errors.append({"code": "ControlNotObserved", "index": index})
        if item.get("absoluteElevationConstraintAuthorized") is not True:
            errors.append({"code": "AbsoluteElevationUnauthorized", "index": index})
    if len(xyz) < 3:
        errors.append({"code": "InsufficientControlCount", "actual": len(xyz), "required": 3})
    if len(support_ids) < 3:
        errors.append({"code": "InsufficientIndependentSupportCount",
                       "actual": len(support_ids), "required": 3})
    if None in contact_ids or len(contact_ids) != 1:
        errors.append({"code": "MixedOrMissingContactIdentity"})
    xy = np.asarray(xyz, dtype=float)[:, :2] if xyz else np.empty((0, 2))
    unique_count = len(np.unique(xy, axis=0)) if len(xy) else 0
    if unique_count != len(xy):
        errors.append({"code": "DuplicateHorizontalControl"})
    design_rank = int(np.linalg.matrix_rank(
        np.column_stack((np.ones(len(xy)), xy)))) if len(xy) else 0
    if design_rank < 3:
        errors.append({"code": "HorizontalControlsDoNotSpanArea", "designRank": design_rank})
    hull = _convex_hull(xy.tolist()) if design_rank == 3 else []
    return {
        "passed": not errors,
        "controlCount": len(xyz),
        "uniqueHorizontalControlCount": unique_count,
        "independentSupportCount": len(support_ids),
        "designRank": design_rank,
        "contactId": next(iter(contact_ids)) if len(contact_ids) == 1 else None,
        "convexHullXYM": [list(point) for point in hull],
        "interpolationDomain": "ClosedConvexHullOfAuthorizedControls",
        "extrapolationAuthorized": False,
        "errors": errors,
    }


class EvidenceBoundedRbfSurface:
    """RBF surface whose evaluation is limited to its evidence convex hull."""
    def __init__(self, controls, shape_parameter, regularization=0.0, *,
                 maximum_condition_number, maximum_control_residual_m):
        self.audit = audit_surface_controls(controls)
        if not self.audit["passed"]:
            raise ValueError("surface control evidence is not ready")
        xyz = np.asarray([[item["xM"], item["yM"], item["zM"]]
                          for item in controls], dtype=float)
        self.surface = RbfStructuralSurface(xyz, shape_parameter, regularization)
        for value, name in ((maximum_condition_number, "maximum_condition_number"),
                            (maximum_control_residual_m, "maximum_control_residual_m")):
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be a finite non-negative number")
        residuals = self.surface.residuals(xyz)
        maximum_residual = float(np.max(np.abs(residuals)))
        self.numerical_audit = {
            "conditionNumber": self.surface.condition_number,
            "maximumAllowedConditionNumber": float(maximum_condition_number),
            "maximumAbsoluteControlResidualM": maximum_residual,
            "maximumAllowedControlResidualM": float(maximum_control_residual_m),
            "passed": (self.surface.condition_number <= maximum_condition_number
                       and maximum_residual <= maximum_control_residual_m),
        }
        if not self.numerical_audit["passed"]:
            raise ValueError("surface numerical stability gate failed")
        self.hull = [tuple(point) for point in self.audit["convexHullXYM"]]
        coordinate_scale = max(np.ptp(xyz[:, 0]), np.ptp(xyz[:, 1]), 1.0)
        self.hull_tolerance = float(np.finfo(float).eps * coordinate_scale**2 * 64)

    def evaluate(self, query_xy):
        query = np.asarray(query_xy, dtype=float)
        if query.ndim != 2 or query.shape[1] != 2 or not np.isfinite(query).all():
            raise ValueError("query must be finite N x 2")
        inside = np.array([_inside_convex_polygon(tuple(point), self.hull,
                                                   self.hull_tolerance)
                           for point in query], dtype=bool)
        values = np.full(len(query), np.nan, dtype=float)
        if np.any(inside):
            values[inside] = self.surface.evaluate(query[inside])
        return {"elevationM": values, "insideEvidenceHull": inside,
                "outsideMeaning": "Unknown_NoExtrapolation"}
