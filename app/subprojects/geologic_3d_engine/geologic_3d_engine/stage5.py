"""Stage-5 orchestration for fold and fault kinematics."""

from .physics.structural_3d import deform_model
from .stage4 import run_stage_four


def run_stage_five(config, stack_spec, event_spec, compaction_spec, structural_spec):
    stage_four = run_stage_four(config, stack_spec, event_spec, compaction_spec)
    if not stage_four["passed"]:
        return {"passed": False, "decision": "Rejected", "stage": "fold_fault_kinematics",
                "errors": [{"code": "BlockedByStageFour"}], "stageFour": stage_four}
    try:
        operations = structural_spec.materialize(config, stage_four["compactedModel"])
        model = deform_model(stage_four["compactedModel"], operations, structural_spec.tolerance)
    except Exception as error:
        return {"passed": False, "decision": "Rejected", "stage": "fold_fault_kinematics",
                "errors": [{"code": "StructuralKinematicsFailed", "message": str(error)}],
                "stageFour": stage_four}
    passed = model.validation["passed"]
    return {"passed": passed, "decision": "Experimental" if passed else "Rejected",
            "stage": "fold_fault_kinematics", "stageFour": stage_four,
            "gates": [model.validation],
            "modelSummary": {"operationCount": len(operations),
                             "sampleCount": model.validation.get("sampleCount", 0),
                             "representation": "DeformedMaterialPointLattice"},
            "structuralModel": model}


def stage_five_manifest(result):
    return {"stage": result["stage"], "passed": result["passed"],
            "decision": result["decision"], "errors": result.get("errors", []),
            "gates": result.get("gates", []), "modelSummary": result.get("modelSummary"),
            "geometryGenerated": bool(result["passed"]),
            "geometryType": "DeformedMaterialPointLattice" if result["passed"] else None,
            "nextAuthorizedStage": "intrusion_crosscutting" if result["passed"] else None}
