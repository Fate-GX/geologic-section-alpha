"""Universal thickness-field coupling without independent contact perturbation."""

from __future__ import annotations

import math
from typing import Sequence


def cholesky_psd(matrix: Sequence[Sequence[float]], tolerance: float = 1e-12) -> list[list[float]]:
    """Validated Cholesky factor for symmetric positive-semidefinite matrices."""
    n = len(matrix)
    if n == 0 or any(len(row) != n for row in matrix):
        raise ValueError("matrix must be non-empty and square")
    for i in range(n):
        for j in range(n):
            if abs(float(matrix[i][j]) - float(matrix[j][i])) > tolerance:
                raise ValueError("covariance matrix must be symmetric")
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            residual = float(matrix[i][j]) - sum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                if residual < -tolerance:
                    raise ValueError("covariance matrix is not positive semidefinite")
                lower[i][j] = math.sqrt(max(0.0, residual))
            elif lower[j][j] > tolerance:
                lower[i][j] = residual / lower[j][j]
            elif abs(residual) > tolerance:
                raise ValueError("singular covariance matrix is inconsistent")
    return lower


def correlated_lognormal_thickness(means: Sequence[float], log_stds: Sequence[float],
                                   correlation: Sequence[Sequence[float]],
                                   independent_latent: Sequence[float],
                                   active: Sequence[bool] | None = None) -> list[float]:
    """Generate positive, cross-layer-correlated thickness at one location."""
    n = len(means)
    if not (len(log_stds) == len(independent_latent) == n):
        raise ValueError("means, log_stds and latent vectors must have equal length")
    if active is not None and len(active) != n:
        raise ValueError("active mask length mismatch")
    if any(float(x) <= 0 for x in means) or any(float(x) < 0 for x in log_stds):
        raise ValueError("means must be positive and log_stds non-negative")
    lower = cholesky_psd(correlation)
    correlated = [sum(lower[i][j] * float(independent_latent[j]) for j in range(i + 1))
                  for i in range(n)]
    values = []
    for i, (mean, sigma, latent) in enumerate(zip(means, log_stds, correlated)):
        value = float(mean) * math.exp(float(sigma) * latent - 0.5 * float(sigma) ** 2)
        values.append(value if active is None or active[i] else 0.0)
    return values


def exponential_spatial_correlation(distance: float, correlation_length: float) -> float:
    """Dimensionless exponential correlation exp(-distance/range)."""
    distance = float(distance)
    correlation_length = float(correlation_length)
    if distance < 0 or correlation_length <= 0:
        raise ValueError("distance must be non-negative and correlation length positive")
    return math.exp(-distance / correlation_length)


def stack_from_thickness_fields(top: Sequence[float],
                                thickness_fields: Sequence[Sequence[float]]) -> list[dict]:
    """Stack shared contacts from non-negative thickness fields."""
    current = [float(x) for x in top]
    units = []
    for index, field in enumerate(thickness_fields):
        if len(field) != len(current) or any(float(x) < 0 for x in field):
            raise ValueError("every thickness field must be non-negative and match top length")
        bottom = [surface - float(thickness) for surface, thickness in zip(current, field)]
        units.append({"unitIndex": index, "top": list(current), "bottom": bottom,
                      "active": [float(x) > 0 for x in field]})
        current = bottom
    return units


def validate_shared_contact_stack(units: Sequence[dict], tolerance: float = 1e-9) -> dict:
    errors = []
    for index, unit in enumerate(units):
        if any(bottom > top + tolerance for top, bottom in zip(unit["top"], unit["bottom"])):
            errors.append({"code": "NegativeThickness", "unitIndex": index})
        if index and any(abs(a - b) > tolerance
                         for a, b in zip(units[index - 1]["bottom"], unit["top"])):
            errors.append({"code": "UnsharedContact", "unitIndex": index})
    return {"passed": not errors, "errors": errors,
            "independentBoundaryPerturbationAllowed": False}
