"""Stage-4 orchestration for evidence-gated compaction."""

from __future__ import annotations

from .config import EngineConfig
from .events.event_spec import Stage3EventSpec
from .physics.compaction_3d import compact_event_model
from .physics.compaction_spec import CompactionSpec
from .stage3 import run_stage_three
from .stratigraphy.stack_spec import StackBuildSpec


def run_stage_four(config: EngineConfig, stack_spec: StackBuildSpec,
                   event_spec: Stage3EventSpec, compaction_spec: CompactionSpec) -> dict:
    stage_three = run_stage_three(config, stack_spec, event_spec)
    if not stage_three["passed"]:
        return {"passed": False, "decision": "Rejected", "stage": "compaction",
                "errors": [{"code": "BlockedByStageThree"}], "stageThree": stage_three}
    try:
        states = compaction_spec.materialize(config, stage_three["eventModel"])
        model, gate = compact_event_model(stage_three["eventModel"], states,
                                          compaction_spec.event_id,
                                          compaction_spec.tolerance)
    except Exception as error:
        return {"passed": False, "decision": "Rejected", "stage": "compaction",
                "errors": [{"code": "CompactionFailed", "message": str(error)}],
                "stageThree": stage_three}
    passed = gate["passed"]
    return {"passed": passed, "decision": "Experimental" if passed else "Rejected",
            "stage": "compaction", "stageThree": stage_three, "gates": [gate],
            "modelSummary": {"unitIds": [body.unit_id for body in
                                           model.primary_bodies + model.replacement_bodies],
                             "anchor": "TopSurfaceFixed",
                             "solidVolumePreserved": gate["passed"]},
            "compactedModel": model,
            "voxelization": gate["partition"]}


def stage_four_manifest(result: dict) -> dict:
    return {"stage": result["stage"], "passed": result["passed"],
            "decision": result["decision"], "errors": result.get("errors", []),
            "gates": result.get("gates", []), "modelSummary": result.get("modelSummary"),
            "geometryGenerated": bool(result["passed"]),
            "geometryType": "CompactedRegularGridEventVolumes" if result["passed"] else None,
            "nextAuthorizedStage": "fold_fault_kinematics" if result["passed"] else None}
