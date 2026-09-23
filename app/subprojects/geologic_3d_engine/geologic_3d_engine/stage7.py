"""Stage-7 orchestration for closed voxel boundary meshes."""

from .geometry.voxel_brep import build_closed_breps
from .stage6 import run_stage_six


def run_stage_seven(config, stack_spec, event_spec, compaction_spec, structural_spec,
                    intrusion_spec, mesh_spec):
    stage_six = run_stage_six(config, stack_spec, event_spec, compaction_spec,
                              structural_spec, intrusion_spec)
    if not stage_six["passed"]:
        return {"passed":False,"decision":"Rejected","stage":"closed_mesh_and_brep",
                "errors":[{"code":"BlockedByStageSix"}],"stageSix":stage_six}
    try:
        source = stage_six["intrusionModel"]
        mesh_spec.validate(source)
        model = build_closed_breps(source.labels_zyx, source.source_model.source_model.grid,
                                   mesh_spec.unit_ids)
    except Exception as error:
        return {"passed":False,"decision":"Rejected","stage":"closed_mesh_and_brep",
                "errors":[{"code":"MeshConstructionFailed","message":str(error)}],
                "stageSix":stage_six}
    passed=model.validation["passed"]
    return {"passed":passed,"decision":"Experimental" if passed else "Rejected",
            "stage":"closed_mesh_and_brep","stageSix":stage_six,
            "gates":[model.validation],
            "modelSummary":{"unitMeshCount":len(model.unit_meshes),
                            "vertexCount":sum(len(m.vertices) for m in model.unit_meshes),
                            "triangleCount":sum(len(m.triangles) for m in model.unit_meshes),
                            "coordinateFrame":model.coordinate_frame},"brepModel":model}


def stage_seven_manifest(result):
    return {"stage":result["stage"],"passed":result["passed"],
            "decision":result["decision"],"errors":result.get("errors",[]),
            "gates":result.get("gates",[]),"modelSummary":result.get("modelSummary"),
            "geometryGenerated":bool(result["passed"]),
            "geometryType":"ClosedOrientedVoxelBoundaryBrep" if result["passed"] else None,
            "nextAuthorizedStage":"adaptive_refinement_and_boolean" if result["passed"] else None}
