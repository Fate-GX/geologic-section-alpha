"""Validated adapter from stochastic thickness output to a conformable stack."""

from __future__ import annotations
import math
from typing import Sequence

from ..export.contract_integrity import canonical_json_bytes, sha256_hex
from ..geometry.regular_grid import RegularGrid3D
from .conformable_stack import ConformableStack, build_conformable_stack, voxelize_stack

EXPECTED_METHOD = "ExactKroneckerSeparableGaussian"
EXPECTED_STATUS = "ExperimentalGenerated_NotGeologicallyAccepted"


def build_stack_from_stochastic_thickness(
    *, grid: RegularGrid3D, top_surface: Sequence[Sequence[float]],
    stochastic_result: dict, expected_unit_ids: Sequence[str],
    zero_thickness_tolerance: float = 1e-9,
) -> tuple[ConformableStack, dict]:
    if stochastic_result.get("samplingMethod") != EXPECTED_METHOD:
        raise ValueError("unsupported stochastic sampling method")
    if stochastic_result.get("status") != EXPECTED_STATUS:
        raise ValueError("stochastic result status is not authorized for experimental stacking")
    source_hash = stochastic_result.get("payloadSha256")
    unsigned = {key: value for key, value in stochastic_result.items() if key != "payloadSha256"}
    if source_hash != sha256_hex(canonical_json_bytes(unsigned)):
        raise ValueError("stochastic result payload hash mismatch")
    source_grid = stochastic_result.get("grid", {})
    if (source_grid.get("nx") != grid.nx or source_grid.get("ny") != grid.ny or
            not math.isclose(float(source_grid.get("spacingX", -1)), grid.cell_size[0]) or
            not math.isclose(float(source_grid.get("spacingY", -1)), grid.cell_size[1])):
        raise ValueError("stochastic grid does not match conformable-stack grid")
    layers = stochastic_result.get("layers")
    if not isinstance(layers, list):
        raise ValueError("stochastic layers are required")
    unit_ids = [str(layer.get("unitId")) for layer in layers]
    if unit_ids != list(expected_unit_ids):
        raise ValueError("stochastic layer order does not match expected stratigraphy")
    thickness_fields = [layer.get("thicknessValues") for layer in layers]
    stack = build_conformable_stack(grid, top_surface, unit_ids, thickness_fields,
                                    zero_thickness_tolerance)
    validation = stack.validate(); voxelization = voxelize_stack(stack)
    if not validation["passed"] or not voxelization["passed"]:
        raise ValueError("stochastic conformable-stack gates failed")
    report = {
        "adapter": "StochasticThicknessToConformableStack-0.1",
        "sourcePayloadSha256": source_hash,
        "samplingMethod": EXPECTED_METHOD,
        "unitOrder": unit_ids,
        "stackValidation": validation,
        "voxelPartition": {"passed": voxelization["passed"],
                           "overlapCount": voxelization["overlapCount"],
                           "envelopeVoidCount": voxelization["envelopeVoidCount"],
                           "unitGeometricVolumes": voxelization["unitGeometricVolumes"],
                           "unitVoxelizedVolumes": voxelization["unitVoxelizedVolumes"]},
        "syntheticStatusPreserved": True,
    }
    return stack, report
