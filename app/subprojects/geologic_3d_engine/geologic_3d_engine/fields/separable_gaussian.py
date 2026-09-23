"""Exact Kronecker sampling for separable Gaussian covariance on a regular grid."""

from __future__ import annotations
import numpy as np


def machine_eigen_tolerance(dimension: int) -> float:
    if dimension <= 0:
        raise ValueError("matrix dimension must be positive")
    return float(np.finfo(float).eps * dimension * 64.0)


def gaussian_axis_covariance(count: int, spacing: float, range_value: float) -> np.ndarray:
    if count <= 0 or spacing <= 0 or range_value <= 0:
        raise ValueError("axis count, spacing and range must be positive")
    coordinate = np.arange(count, dtype=float) * float(spacing)
    delta = coordinate[:, None] - coordinate[None, :]
    return np.exp(-((delta / float(range_value)) ** 2))


def separable_covariance(nx: int, ny: int, spacing_x: float, spacing_y: float,
                         range_x: float, range_y: float, variance: float) -> np.ndarray:
    if variance < 0:
        raise ValueError("variance must be non-negative")
    kx = gaussian_axis_covariance(nx, spacing_x, range_x)
    ky = gaussian_axis_covariance(ny, spacing_y, range_y)
    return float(variance) * np.kron(ky, kx)


def sample_separable_gaussian(*, nx: int, ny: int, spacing_x: float, spacing_y: float,
                              range_x: float, range_y: float, variance: float,
                              standard_normal: np.ndarray,
                              negative_eigen_tolerances: tuple[float, float]) -> np.ndarray:
    """Return an ``(ny,nx)`` exact covariance sample for supplied iid N(0,1)."""
    if variance < 0:
        raise ValueError("variance must be non-negative")
    noise = np.asarray(standard_normal, dtype=float)
    if noise.shape != (ny, nx) or not np.all(np.isfinite(noise)):
        raise ValueError("standard_normal must be a finite (ny,nx) array")
    kx = gaussian_axis_covariance(nx, spacing_x, range_x)
    ky = gaussian_axis_covariance(ny, spacing_y, range_y)
    lx, qx = np.linalg.eigh(kx); ly, qy = np.linalg.eigh(ky)
    if (len(negative_eigen_tolerances) != 2 or
            any(not np.isfinite(value) or value < 0 for value in negative_eigen_tolerances)):
        raise ValueError("two finite non-negative eigenvalue tolerances are required")
    tolerance_x, tolerance_y = map(float, negative_eigen_tolerances)
    if float(np.min(lx)) < -tolerance_x or float(np.min(ly)) < -tolerance_y:
        raise ValueError("axis covariance is not positive semidefinite")
    # The caller supplies the already unified declared/machine-scale policy.
    lx = np.where(lx < 0.0, 0.0, lx); ly = np.where(ly < 0.0, 0.0, ly)
    left = qy @ np.diag(np.sqrt(ly))
    right = np.diag(np.sqrt(lx)) @ qx.T
    return np.sqrt(float(variance)) * (left @ noise @ right)


def complexity_estimate(nx: int, ny: int) -> dict:
    if nx <= 0 or ny <= 0:
        raise ValueError("grid dimensions must be positive")
    n = nx * ny
    return {
        "pointCount": n,
        "denseMatrixElements": n * n,
        "separableMatrixElements": nx * nx + ny * ny,
        "denseCubicWorkProxy": n ** 3,
        "separableCubicWorkProxy": nx ** 3 + ny ** 3,
    }
