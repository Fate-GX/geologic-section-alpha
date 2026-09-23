"""Stage-9 orchestration for seeded uncertainty ensembles."""

from .stage8 import run_stage_eight
from .uncertainty.seeded_ensemble import build_seeded_ensemble


def run_stage_nine(config, stack_spec, event_spec, compaction_spec, structural_spec,
                   intrusion_spec, mesh_spec, refinement_spec, ensemble_spec):
    stage8 = run_stage_eight(config, stack_spec, event_spec, compaction_spec,
                             structural_spec, intrusion_spec, mesh_spec, refinement_spec)
    if not stage8["passed"]:
        return {"passed": False, "decision": "Rejected", "stage": "uncertainty_ensemble",
                "errors": [{"code": "BlockedByStageEight"}], "stageEight": stage8}
    try:
        ensemble = build_seeded_ensemble(config, stack_spec, event_spec, compaction_spec,
            structural_spec, intrusion_spec, mesh_spec, refinement_spec, ensemble_spec)
    except Exception as error:
        return {"passed": False, "decision": "Rejected", "stage": "uncertainty_ensemble",
                "errors": [{"code": "UncertaintyEnsembleFailed", "message": str(error)}],
                "stageEight": stage8}
    gate = ensemble["validation"]
    return {"passed": gate["passed"], "decision": "Experimental" if gate["passed"] else "Rejected",
            "stage": "uncertainty_ensemble", "stageEight": stage8, "gates": [gate],
            "modelSummary": {"memberCount": gate["memberCount"],
                "validMemberCount": gate["validMemberCount"],
                "meanNormalizedEntropy": gate["meanNormalizedEntropy"],
                "disagreementCellCount": gate["disagreementCellCount"],
                "representation": ensemble["representation"]}, "ensemble": ensemble}


def stage_nine_manifest(result):
    return {"stage": result["stage"], "passed": result["passed"],
        "decision": result["decision"], "errors": result.get("errors", []),
        "gates": result.get("gates", []), "modelSummary": result.get("modelSummary"),
        "geometryGenerated": bool(result["passed"]),
        "geometryType": "SeededEvidenceBoundedMaterialProbabilityEnsemble" if result["passed"] else None,
        "nextAuthorizedStage": "section_intersection" if result["passed"] else None}
