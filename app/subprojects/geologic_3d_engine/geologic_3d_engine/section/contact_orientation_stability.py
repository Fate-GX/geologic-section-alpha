"""Audit whether DEM-lifted mapped-contact orientations survive scale changes."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np

from .map_template import apparent_dip_degrees


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def audit_multiscale_contact_orientation(diagnostics_by_scale: Sequence[Mapping],
                                         section_azimuth_degrees: float, *,
                                         maximum_normal_separation_degrees: float,
                                         maximum_apparent_dip_spread_degrees: float,
                                         maximum_orthogonal_rmse_m: float):
    """Compare one mapped contact fitted at three or more spatial scales.

    Plane normals are axial, so ``abs(dot(n_i,n_j))`` is used.  Passing this
    numerical diagnostic never authorizes a subsurface continuation by itself.
    """
    azimuth = _finite(section_azimuth_degrees, "section azimuth") % 360.0
    limits = [_finite(maximum_normal_separation_degrees, "normal limit"),
              _finite(maximum_apparent_dip_spread_degrees, "apparent-dip limit"),
              _finite(maximum_orthogonal_rmse_m, "RMSE limit")]
    if any(v < 0 for v in limits):
        raise ValueError("stability limits must be non-negative")
    if not isinstance(diagnostics_by_scale, Sequence) or len(diagnostics_by_scale) < 3:
        raise ValueError("at least three scale diagnostics are required")
    feature_ids = {row.get("featureId") for row in diagnostics_by_scale
                   if isinstance(row, Mapping)}
    if len(feature_ids) != 1 or None in feature_ids:
        raise ValueError("all scale diagnostics must describe one feature")
    stations = [float(row["stationM"]) for row in diagnostics_by_scale
                if "stationM" in row]
    if stations and (len(stations) != len(diagnostics_by_scale) or
                     max(stations)-min(stations) > 1e-6):
        raise ValueError("all scale diagnostics must describe one route crossing")
    rows = []
    normals = []
    radii = set()
    for item in diagnostics_by_scale:
        fit = item.get("planeFit")
        if item.get("fitState") != "DiagnosticFitAvailable" or not isinstance(fit, Mapping):
            raise ValueError("every scale requires a completed diagnostic plane fit")
        radius = _finite(item.get("radiusM"), "radiusM")
        if radius <= 0 or radius in radii:
            raise ValueError("positive unique fitting radii are required")
        radii.add(radius)
        normal = np.asarray(fit.get("unitNormal"), dtype=float)
        if normal.shape != (3,) or not np.isfinite(normal).all() or not math.isclose(
                float(np.linalg.norm(normal)), 1.0, rel_tol=0, abs_tol=1e-8):
            raise ValueError("plane unitNormal is invalid")
        normals.append(normal)
        dip = _finite(fit.get("dipDegrees"), "dipDegrees")
        direction = _finite(fit.get("dipDirectionDegrees"), "dipDirectionDegrees")
        rmse = _finite(fit.get("orthogonalRmseM"), "orthogonalRmseM")
        rows.append({"radiusM": radius, "dipDegrees": dip,
                     "dipDirectionDegrees": direction, "orthogonalRmseM": rmse,
                     "apparentDipDegrees": apparent_dip_degrees(dip, direction, azimuth)})
    separations = []
    for i in range(len(normals)):
        for j in range(i+1, len(normals)):
            cosine = min(1.0, max(0.0, abs(float(np.dot(normals[i], normals[j])))))
            separations.append(math.degrees(math.acos(cosine)))
    apparent = [row["apparentDipDegrees"] for row in rows]
    maximum_separation = max(separations)
    apparent_spread = max(apparent)-min(apparent)
    maximum_rmse = max(row["orthogonalRmseM"] for row in rows)
    passed = (maximum_separation <= limits[0] and apparent_spread <= limits[1]
              and maximum_rmse <= limits[2])
    return {
        "featureId": next(iter(feature_ids)), "sectionAzimuthDegrees": azimuth,
        "scaleDiagnostics": sorted(rows, key=lambda row: row["radiusM"]),
        "maximumAxialNormalSeparationDegrees": maximum_separation,
        "apparentDipSpreadDegrees": apparent_spread,
        "maximumOrthogonalRmseM": maximum_rmse,
        "declaredLimits": {"maximumNormalSeparationDegrees": limits[0],
                           "maximumApparentDipSpreadDegrees": limits[1],
                           "maximumOrthogonalRmseM": limits[2]},
        "stabilityStatus": "ScaleStableDiagnostic" if passed else "RejectedScaleUnstable",
        "eligibleForReviewedHypothesis": passed,
        "subsurfaceContinuationAuthorized": False,
        "authorizationBoundary": "MapDEMComparator_NotDirectStructuralObservation",
    }
