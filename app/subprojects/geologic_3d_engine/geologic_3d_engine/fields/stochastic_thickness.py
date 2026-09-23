"""Minimal experimental transformed-latent-Gaussian thickness generator.

This module implements only the independently reviewed v0.8 contract subset:
Gaussian within-layer covariance, independent layers, seeded replay, PSD audit,
and the Allard positive-part power transform. It is not a production geology
model and does not infer parameters.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from ..export.authentication_state import verify_with_rotation_policy
from ..export.contract_integrity import canonical_json_bytes, sha256_hex
from .separable_gaussian import (
    gaussian_axis_covariance, machine_eigen_tolerance, sample_separable_gaussian)

ALGORITHM_VERSION = "STOCHASTIC-THICKNESS-SEPARABLE-0.2.1"
CONTRACT_VERSION = "0.8.0-candidate"
UPSTREAM_VALIDATION_KIND = "StochasticThicknessRequestContractValidation"
UPSTREAM_VALIDATOR_VERSION = "STOCHASTIC-THICKNESS-CONTRACT-VALIDATOR-0.1.0"
AUTHENTICATION_PURPOSE = "stochastic-thickness-upstream-validation"


def _strict_keys(value: dict, allowed: set[str], name: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"{name} contains unsupported keys: {', '.join(unknown)}")


def _grid_shape(grid: dict) -> tuple[int, int, float, float]:
    _strict_keys(grid, {"nx", "ny", "spacingX", "spacingY"}, "grid")
    nx, ny = int(grid["nx"]), int(grid["ny"])
    sx, sy = float(grid["spacingX"]), float(grid["spacingY"])
    if nx <= 0 or ny <= 0 or sx <= 0 or sy <= 0:
        raise ValueError("grid dimensions and spacing must be positive")
    return nx, ny, sx, sy


def _psd_audit(matrix: np.ndarray, policy: dict) -> dict:
    _strict_keys(policy, {"symmetryTolerance", "absoluteEigenTolerance",
                          "relativeEigenTolerance", "toleranceJustification"}, "psdAudit")
    if not policy.get("toleranceJustification"):
        raise ValueError("psdAudit toleranceJustification is required")
    symmetry = float(np.max(np.abs(matrix - matrix.T)))
    eigenvalues = np.linalg.eigvalsh(matrix)
    maximum = float(np.max(np.abs(eigenvalues))) if eigenvalues.size else 0.0
    tolerance = float(policy["absoluteEigenTolerance"]) + float(policy["relativeEigenTolerance"]) * max(1.0, maximum)
    minimum = float(np.min(eigenvalues)) if eigenvalues.size else 0.0
    passed = symmetry <= float(policy["symmetryTolerance"]) and minimum >= -tolerance
    return {"passed": passed, "matrixDimension": int(matrix.shape[0]),
            "symmetryResidual": symmetry, "minimumEigenvalue": minimum,
            "maximumAbsoluteEigenvalue": maximum, "effectiveEigenTolerance": tolerance,
            "toleranceJustification": str(policy["toleranceJustification"])}


def generate_stochastic_thickness(request: dict, *, authentication_context: dict) -> dict:
    allowed = {"contractVersion", "algorithmVersion", "randomSeed", "grid", "layers",
               "psdAudit", "authenticatedUpstreamValidation"}
    _strict_keys(request, allowed, "request")
    if request.get("contractVersion") != CONTRACT_VERSION:
        raise ValueError("unsupported stochastic thickness contract version")
    if request.get("algorithmVersion") != ALGORITHM_VERSION:
        raise ValueError("unsupported stochastic thickness algorithm version")
    authenticated = request.get("authenticatedUpstreamValidation")
    if not isinstance(authenticated, dict):
        raise ValueError("authenticated upstream v0.8 validation is required")
    required_context = {"secrets", "policies", "nowUtc", "nonceStore"}
    if not isinstance(authentication_context, dict) or set(authentication_context) != required_context:
        raise ValueError("complete authentication_context is required")
    request_payload = {key: value for key, value in request.items()
                       if key != "authenticatedUpstreamValidation"}
    verify_with_rotation_policy(
        authenticated, secrets=authentication_context["secrets"],
        policies=authentication_context["policies"], expected_purpose=AUTHENTICATION_PURPOSE,
        now_utc=authentication_context["nowUtc"], nonce_store=authentication_context["nonceStore"],
        expected_payload=request_payload,
        expected_validation={"validationKind": UPSTREAM_VALIDATION_KIND,
                             "contractVersion": CONTRACT_VERSION,
                             "validatorVersion": UPSTREAM_VALIDATOR_VERSION})
    if not isinstance(request.get("randomSeed"), int):
        raise ValueError("randomSeed must be an integer")
    nx, ny, spacing_x, spacing_y = _grid_shape(dict(request.get("grid", {})))
    layers = request.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError("layers must be a non-empty list")
    rng = np.random.default_rng(request["randomSeed"])
    generated = []
    for index, layer in enumerate(layers):
        _strict_keys(layer, {"unitId", "threshold", "transform", "crossLayerPolicy",
                             "withinLayerCovariance", "parameterEvidenceIds"}, f"layers[{index}]")
        if layer.get("crossLayerPolicy") != "Independent":
            raise ValueError("only independent cross-layer policy is implemented")
        if not layer.get("parameterEvidenceIds"):
            raise ValueError("parameterEvidenceIds are required")
        transform = dict(layer.get("transform", {}))
        _strict_keys(transform, {"kind", "mu", "beta"}, f"layers[{index}].transform")
        if transform.get("kind") != "PowerPositivePart":
            raise ValueError("only PowerPositivePart transform is implemented")
        mu, beta = float(transform["mu"]), float(transform["beta"])
        threshold = float(layer["threshold"])
        if mu <= 0 or beta <= 0 or not all(math.isfinite(v) for v in (mu, beta, threshold)):
            raise ValueError("mu and beta must be positive finite; threshold must be finite")
        covariance = dict(layer.get("withinLayerCovariance", {}))
        _strict_keys(covariance, {"model", "variance", "ranges"}, f"layers[{index}].withinLayerCovariance")
        if covariance.get("model") != "Gaussian":
            raise ValueError("only Gaussian covariance is implemented")
        variance = float(covariance["variance"])
        ranges = list(covariance["ranges"])
        if variance < 0 or len(ranges) != 2 or any(float(value) <= 0 for value in ranges):
            raise ValueError("variance must be non-negative and ranges must contain two positive values")
        axis_x = gaussian_axis_covariance(nx, spacing_x, float(ranges[0]))
        axis_y = gaussian_axis_covariance(ny, spacing_y, float(ranges[1]))
        audit_x = _psd_audit(axis_x, dict(request.get("psdAudit", {})))
        audit_y = _psd_audit(axis_y, dict(request.get("psdAudit", {})))
        if not audit_x["passed"] or not audit_y["passed"]:
            raise ValueError(f"covariance PSD audit failed for {layer.get('unitId')}")
        clip_x = min(audit_x["effectiveEigenTolerance"], machine_eigen_tolerance(nx))
        clip_y = min(audit_y["effectiveEigenTolerance"], machine_eigen_tolerance(ny))
        latent = sample_separable_gaussian(
            nx=nx, ny=ny, spacing_x=spacing_x, spacing_y=spacing_y,
            range_x=float(ranges[0]), range_y=float(ranges[1]), variance=variance,
            standard_normal=rng.standard_normal((ny, nx)),
            negative_eigen_tolerances=(clip_x, clip_y))
        excess = np.maximum(latent - threshold, 0.0)
        thickness = mu * np.power(excess, beta)
        generated.append({"unitId": str(layer.get("unitId")),
                          "thicknessValues": thickness.reshape((ny, nx)).tolist(),
                          "minimumThickness": float(np.min(thickness)),
                          "maximumThickness": float(np.max(thickness)),
                          "zeroThicknessCount": int(np.count_nonzero(thickness == 0.0)),
                          "psdAudit": {"passed": True, "axisX": audit_x, "axisY": audit_y,
                                       "fullMatrixMaterialized": False,
                                       "negativeEigenPolicy": "MinDeclaredAuditAndMachineRoundoff",
                                       "policyId": "SEPARABLE-GAUSSIAN-EIGEN-TOLERANCE-0.1",
                                       "effectiveClipToleranceX": clip_x,
                                       "effectiveClipToleranceY": clip_y},
                          "parameterEvidenceIds": list(layer["parameterEvidenceIds"])})
    payload: dict[str, Any] = {"contractVersion": CONTRACT_VERSION,
                               "algorithmVersion": ALGORITHM_VERSION,
                               "randomSeed": request["randomSeed"],
                               "grid": dict(request["grid"]), "layers": generated,
                               "crossLayerPolicy": "Independent",
                               "samplingMethod": "ExactKroneckerSeparableGaussian",
                               "status": "ExperimentalGenerated_NotGeologicallyAccepted"}
    payload["payloadSha256"] = sha256_hex(canonical_json_bytes(payload))
    return payload
