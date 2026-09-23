"""Convention-explicit planar geological observation geometry."""
from __future__ import annotations

import math
import numpy as np


def plane_from_three_points(points_xyz, relative_tolerance=1e-12):
    points = np.asarray(points_xyz, dtype=float)
    if points.shape != (3, 3) or not np.isfinite(points).all():
        raise ValueError("three finite XYZ points are required")
    u, v = points[1] - points[0], points[2] - points[0]
    normal = np.cross(u, v)
    scale = max(np.linalg.norm(u) * np.linalg.norm(v), 1.0)
    if np.linalg.norm(normal) <= relative_tolerance * scale:
        raise ValueError("three-point plane is coincident or collinear")
    normal /= np.linalg.norm(normal)
    if normal[2] < 0:
        normal = -normal
    offset = -float(np.dot(normal, points[0]))
    residuals = points @ normal + offset
    return {"originXYZ": points[0].tolist(), "unitNormal": normal.tolist(),
            "offset": offset, "maximumResidual": float(np.max(np.abs(residuals))),
            **strike_dip_from_normal(normal)}


def plane_from_points_orthogonal_least_squares(points_xyz, relative_tolerance=1e-12):
    """Fit a local plane using true orthogonal distances and all observations."""
    points = np.asarray(points_xyz, dtype=float)
    if (points.ndim != 2 or points.shape[1] != 3 or len(points) < 3 or
            not np.isfinite(points).all()):
        raise ValueError("three or more finite XYZ points are required")
    centroid = points.mean(axis=0)
    centered = points - centroid
    _, singular_values, vh = np.linalg.svd(centered, full_matrices=False)
    scale = max(float(singular_values[0]), 1.0)
    if len(singular_values) < 2 or singular_values[1] <= relative_tolerance * scale:
        raise ValueError("contact observations do not span a plane")
    normal = vh[-1]
    if normal[2] < 0:
        normal = -normal
    offset = -float(np.dot(normal, centroid))
    residuals = points @ normal + offset
    horizontal = centered[:, :2]
    horizontal_span = float(np.max(np.linalg.norm(
        horizontal[:, None, :] - horizontal[None, :, :], axis=2)))
    return {
        "pointCount": int(len(points)),
        "centroidXYZ": centroid.tolist(),
        "unitNormal": normal.tolist(),
        "offset": offset,
        "orthogonalResidualsM": residuals.tolist(),
        "orthogonalRmseM": float(np.sqrt(np.mean(residuals ** 2))),
        "maximumAbsoluteOrthogonalResidualM": float(np.max(np.abs(residuals))),
        "horizontalSpanM": horizontal_span,
        "singularValuesM": singular_values.tolist(),
        "fitMethod": "OrthogonalLeastSquares_SVD",
        "interpretationBoundary": "LocalPlanarComparator_NotAutomaticSubsurfaceTruth",
        **strike_dip_from_normal(normal),
    }


def strike_dip_from_normal(unit_normal):
    n = np.asarray(unit_normal, dtype=float)
    if n.shape != (3,) or not np.isfinite(n).all() or np.linalg.norm(n) == 0:
        raise ValueError("finite non-zero normal required")
    n /= np.linalg.norm(n)
    if n[2] < 0:
        n = -n
    horizontal = math.hypot(n[0], n[1])
    dip = math.degrees(math.atan2(horizontal, n[2]))
    if horizontal <= 1e-15:
        return {"strikeAzimuthDegrees": None, "dipDegrees": 0.0,
                "dipDirectionDegrees": None, "orientationState": "Horizontal"}
    dip_direction = math.degrees(math.atan2(n[0], n[1])) % 360
    strike = (dip_direction - 90) % 360
    return {"strikeAzimuthDegrees": strike, "dipDegrees": dip,
            "dipDirectionDegrees": dip_direction, "orientationState": "Inclined"}


def planar_contact_on_vertical_section(plane_normal, plane_offset, route_origin_xy,
                                       route_azimuth_degrees, stations):
    n = np.asarray(plane_normal, dtype=float)
    origin = np.asarray(route_origin_xy, dtype=float)
    s = np.asarray(stations, dtype=float)
    if n.shape != (3,) or origin.shape != (2,) or s.ndim != 1 or not np.isfinite(s).all():
        raise ValueError("invalid plane/section input")
    if abs(n[2]) <= 1e-15:
        raise ValueError("vertical geological plane does not define single-valued section elevation")
    azimuth = math.radians(route_azimuth_degrees)
    direction = np.array([math.sin(azimuth), math.cos(azimuth)])
    xy = origin + s[:, None] * direction
    z = -(n[0] * xy[:, 0] + n[1] * xy[:, 1] + plane_offset) / n[2]
    return {"station": s.tolist(), "xyz": np.column_stack((xy, z)).tolist()}
