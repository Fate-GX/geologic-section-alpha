"""Stage-10 orchestration for exact representative-model section extraction."""

from .section.plane_intersection import extract_section
from .section.uncertainty_projection import project_uncertainty_to_section
from .stage9 import run_stage_nine


def run_stage_ten(config, stack_spec, event_spec, compaction_spec, structural_spec,
                  intrusion_spec, mesh_spec, refinement_spec, ensemble_spec, section_spec):
    stage9=run_stage_nine(config,stack_spec,event_spec,compaction_spec,structural_spec,
                         intrusion_spec,mesh_spec,refinement_spec,ensemble_spec)
    if not stage9["passed"]:
        return {"passed":False,"decision":"Rejected","stage":"section_intersection",
                "errors":[{"code":"BlockedByStageNine"}],"stageNine":stage9}
    try:
        brep=stage9["stageEight"]["adaptiveModel"].refined_brep
        section=extract_section(brep,section_spec)
        ensemble=stage9["ensemble"]
        uncertainty=project_uncertainty_to_section(ensemble["materialProbabilityZYX"],
          ensemble["normalizedEntropyZYX"],ensemble["disagreementMaskZYX"],
          stage9["stageEight"]["adaptiveModel"].fine_grid,section_spec)
    except Exception as error:
        return {"passed":False,"decision":"Rejected","stage":"section_intersection",
                "errors":[{"code":"SectionExtractionFailed","message":str(error)}],
                "stageNine":stage9}
    gate=section["validation"];uncertainty_gate=uncertainty["validation"]
    passed=gate["passed"] and uncertainty_gate["passed"]
    return {"passed":passed,"decision":"Experimental" if passed else "Rejected",
      "stage":"section_intersection","stageNine":stage9,"gates":[gate,uncertainty_gate],
      "section":section,"uncertaintySection":uncertainty,
      "modelSummary":{"sectionId":section["sectionId"],"polygonCount":gate["polygonCount"],
        "unitCount":gate["unitCount"],"coordinateFrame":gate["coordinateFrame"],
        "representation":section["representation"],
        "uncertaintyProjection":"SectionAlignedSpatialGrid_NearestSourceCell"}}


def stage_ten_manifest(result):
    return {"stage":result["stage"],"passed":result["passed"],"decision":result["decision"],
      "errors":result.get("errors",[]),"gates":result.get("gates",[]),
      "modelSummary":result.get("modelSummary"),"geometryGenerated":bool(result["passed"]),
      "geometryType":"ClosedSectionPolygonsUV" if result["passed"] else None,
      "nextAuthorizedStage":"autocad_export_contract" if result["passed"] else None}
