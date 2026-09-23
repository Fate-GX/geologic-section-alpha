"""Stage-8 orchestration for adaptive refinement and Boolean partition audits."""

from .geometry.adaptive_refinement import refine_partition
from .stage7 import run_stage_seven


def run_stage_eight(config,stack_spec,event_spec,compaction_spec,structural_spec,
                    intrusion_spec,mesh_spec,refinement_spec):
    stage7=run_stage_seven(config,stack_spec,event_spec,compaction_spec,structural_spec,
                           intrusion_spec,mesh_spec)
    if not stage7["passed"]:
        return {"passed":False,"decision":"Rejected","stage":"adaptive_refinement_and_boolean",
                "errors":[{"code":"BlockedByStageSeven"}],"stageSeven":stage7}
    try:
        refinement_spec.validate()
        intrusion=stage7["stageSix"]["intrusionModel"]
        model=refine_partition(intrusion,refinement_spec.refinement_factor,
          refinement_spec.maximum_refined_fraction,refinement_spec.volume_relative_tolerance,
          refinement_spec.require_topology_stability,refinement_spec.convergence_levels)
    except Exception as error:
        return {"passed":False,"decision":"Rejected","stage":"adaptive_refinement_and_boolean",
                "errors":[{"code":"AdaptiveRefinementFailed","message":str(error)}],
                "stageSeven":stage7}
    passed=model.validation["passed"]
    return {"passed":passed,"decision":"Experimental" if passed else "Rejected",
      "stage":"adaptive_refinement_and_boolean","stageSeven":stage7,"gates":[model.validation],
      "modelSummary":{"leafCount":len(model.leaves),
        "refinedCoarseCellCount":model.validation["refinedCoarseCellCount"],
        "refinedFraction":model.validation["refinedFraction"],
        "topologyStable":model.validation["topologyStable"],
        "representation":"AdaptiveLeavesWithConformingAuditGrid"},"adaptiveModel":model}


def stage_eight_manifest(result):
    return {"stage":result["stage"],"passed":result["passed"],"decision":result["decision"],
      "errors":result.get("errors",[]),"gates":result.get("gates",[]),
      "modelSummary":result.get("modelSummary"),"geometryGenerated":bool(result["passed"]),
      "geometryType":"AdaptiveLeavesWithConformingAuditGrid" if result["passed"] else None,
      "nextAuthorizedStage":"uncertainty_ensemble" if result["passed"] else None}
