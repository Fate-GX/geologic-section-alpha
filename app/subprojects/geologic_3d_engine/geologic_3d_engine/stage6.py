"""Stage-6 orchestration for cross-cutting intrusions."""

from .events.intrusion_3d import apply_intrusions
from .stage5 import run_stage_five


def run_stage_six(config, stack_spec, event_spec, compaction_spec,
                  structural_spec, intrusion_spec):
    stage_five = run_stage_five(config, stack_spec, event_spec, compaction_spec,
                                structural_spec)
    if not stage_five["passed"]:
        return {"passed": False, "decision": "Rejected", "stage": "intrusion_crosscutting",
                "errors": [{"code": "BlockedByStageFive"}], "stageFive": stage_five}
    try:
        operations = intrusion_spec.materialize(config, stage_five["structuralModel"])
        model = apply_intrusions(stage_five["structuralModel"], operations)
    except Exception as error:
        return {"passed": False, "decision": "Rejected", "stage": "intrusion_crosscutting",
                "errors": [{"code": "IntrusionConstructionFailed", "message": str(error)}],
                "stageFive": stage_five}
    passed = model.validation["passed"]
    return {"passed": passed, "decision": "Experimental" if passed else "Rejected",
            "stage": "intrusion_crosscutting", "stageFive": stage_five,
            "gates": [model.validation],
            "modelSummary": {"operationCount": len(operations),
                             "intrusionUnitIds": [op.unit_id for op in operations],
                             "representation": "CrosscuttingReplacementVoxelModel"},
            "intrusionModel": model}


def stage_six_manifest(result):
    return {"stage": result["stage"], "passed": result["passed"],
            "decision": result["decision"], "errors": result.get("errors", []),
            "gates": result.get("gates", []), "modelSummary": result.get("modelSummary"),
            "geometryGenerated": bool(result["passed"]),
            "geometryType": "CrosscuttingReplacementVoxelModel" if result["passed"] else None,
            "nextAuthorizedStage": "closed_mesh_and_brep" if result["passed"] else None}
