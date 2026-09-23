"""Stage-2 orchestration for conformable 3D stacks."""

from __future__ import annotations

from .config import EngineConfig
from .runner import configuration_fingerprint, validate_stage_one
from .stratigraphy.conformable_stack import voxelize_stack
from .stratigraphy.stack_spec import StackBuildSpec


def run_stage_two(config: EngineConfig, spec: StackBuildSpec) -> dict:
    stage_one = validate_stage_one(config)
    if not stage_one["passed"]:
        return {"passed": False, "decision": "Rejected", "stage": "positive_thickness_3d_stack",
                "errors": [{"code": "BlockedByStageOne"}], "stageOne": stage_one}
    try:
        stack = spec.build(config)
        stack_gate = stack.validate()
        voxel_gate = voxelize_stack(stack)
    except Exception as error:
        return {"passed": False, "decision": "Rejected", "stage": "positive_thickness_3d_stack",
                "errors": [{"code": "StackConstructionFailed", "message": str(error)}],
                "stageOne": stage_one}
    passed = stack_gate["passed"] and voxel_gate["passed"]
    return {"passed": passed, "decision": "Experimental" if passed else "Rejected",
            "stage": "positive_thickness_3d_stack", "stageOne": stage_one,
            "gates": [stack_gate, {key: value for key, value in voxel_gate.items()
                                    if key != "labelsZYX"}],
            "modelSummary": {"grid": stack.grid.to_dict(),
                             "unitIds": [layer.unit_id for layer in stack.layers],
                             "unitGeometricVolumes": voxel_gate["unitGeometricVolumes"],
                             "unitVoxelizedVolumes": voxel_gate["unitVoxelizedVolumes"],
                             "volumeDiscretizationError": voxel_gate["volumeDiscretizationError"],
                             "configurationSha256": configuration_fingerprint(config)},
            "stack": stack, "voxelization": voxel_gate}


def stage_two_manifest(result: dict) -> dict:
    return {"stage": result["stage"], "passed": result["passed"],
            "decision": result["decision"], "errors": result.get("errors", []),
            "gates": result.get("gates", []), "modelSummary": result.get("modelSummary"),
            "geometryGenerated": bool(result["passed"]),
            "geometryType": "RegularGridConformableVolumes" if result["passed"] else None,
            "nextAuthorizedStage": "erosion_onlap_lens_pinchout" if result["passed"] else None}
