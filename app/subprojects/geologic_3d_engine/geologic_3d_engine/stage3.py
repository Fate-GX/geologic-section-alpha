"""Stage-3 orchestration for erosion and depositional event bodies."""

from __future__ import annotations

from .config import EngineConfig
from .events.event_spec import Stage3EventSpec
from .events.stratigraphic_events import voxelize_event_model
from .stage2 import run_stage_two
from .stratigraphy.stack_spec import StackBuildSpec


def run_stage_three(config: EngineConfig, stack_spec: StackBuildSpec,
                    event_spec: Stage3EventSpec) -> dict:
    stage_two = run_stage_two(config, stack_spec)
    if not stage_two["passed"]:
        return {"passed": False, "decision": "Rejected",
                "stage": "erosion_onlap_lens_pinchout",
                "errors": [{"code": "BlockedByStageTwo"}], "stageTwo": stage_two}
    try:
        model = event_spec.apply(config, stage_two["stack"])
        voxel_gate = voxelize_event_model(model)
    except Exception as error:
        return {"passed": False, "decision": "Rejected",
                "stage": "erosion_onlap_lens_pinchout",
                "errors": [{"code": "EventConstructionFailed", "message": str(error)}],
                "stageTwo": stage_two}
    passed = voxel_gate["passed"]
    return {"passed": passed, "decision": "Experimental" if passed else "Rejected",
            "stage": "erosion_onlap_lens_pinchout", "stageTwo": stage_two,
            "gates": [{key: value for key, value in voxel_gate.items()
                       if key != "labelsZYX"}],
            "modelSummary": {"primaryUnitIds": [body.unit_id for body in model.primary_bodies],
                             "replacementUnitIds": [body.unit_id for body in model.replacement_bodies],
                             "eventCount": len(model.event_log),
                             "unitVoxelizedVolumes": voxel_gate["unitVoxelizedVolumes"]},
            "eventModel": model, "voxelization": voxel_gate}


def stage_three_manifest(result: dict) -> dict:
    return {"stage": result["stage"], "passed": result["passed"],
            "decision": result["decision"], "errors": result.get("errors", []),
            "gates": result.get("gates", []), "modelSummary": result.get("modelSummary"),
            "geometryGenerated": bool(result["passed"]),
            "geometryType": "RegularGridEventVolumes" if result["passed"] else None,
            "nextAuthorizedStage": "compaction" if result["passed"] else None}
