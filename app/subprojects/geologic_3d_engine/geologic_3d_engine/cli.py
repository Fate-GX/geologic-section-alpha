"""Command-line entry point shared with the future GUI backend."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .runner import create_run_manifest, validate_stage_one
from .stage2 import run_stage_two, stage_two_manifest
from .stage3 import run_stage_three, stage_three_manifest
from .events.event_spec import load_event_spec
from .stage4 import run_stage_four, stage_four_manifest
from .physics.compaction_spec import load_compaction_spec
from .stage5 import run_stage_five, stage_five_manifest
from .physics.structural_spec import load_structural_spec
from .stage6 import run_stage_six, stage_six_manifest
from .events.intrusion_spec import load_intrusion_spec
from .stage7 import run_stage_seven, stage_seven_manifest
from .geometry.mesh_spec import load_mesh_spec
from .stage8 import run_stage_eight, stage_eight_manifest
from .geometry.refinement_spec import load_refinement_spec
from .stage9 import run_stage_nine, stage_nine_manifest
from .uncertainty.ensemble_spec import load_ensemble_spec
from .stage10 import run_stage_ten, stage_ten_manifest
from .section.section_spec import load_section_spec
from .stage11 import run_stage_eleven, stage_eleven_manifest
from .export.export_spec import load_export_spec
from .stage12 import run_stage_twelve, stage_twelve_manifest
from .validation.release_spec import load_release_spec
from .stratigraphy.stack_spec import load_stack_spec


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="geologic-3d-engine")
    parser.add_argument("config", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--stack-spec", type=Path)
    parser.add_argument("--event-spec", type=Path)
    parser.add_argument("--compaction-spec", type=Path)
    parser.add_argument("--structural-spec", type=Path)
    parser.add_argument("--intrusion-spec", type=Path)
    parser.add_argument("--mesh-spec", type=Path)
    parser.add_argument("--refinement-spec", type=Path)
    parser.add_argument("--ensemble-spec", type=Path)
    parser.add_argument("--section-spec", type=Path)
    parser.add_argument("--export-spec", type=Path)
    parser.add_argument("--release-spec", type=Path)
    parser.add_argument("--dwg-validation", type=Path)
    parser.add_argument("--model", type=Path,
                        help="Write Stage-2 stack surfaces and voxel labels as JSON")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        validation = validate_stage_one(config)
        manifest = create_run_manifest(config, validation)
        model_payload = None
        if args.stack_spec:
            result = run_stage_two(config, load_stack_spec(args.stack_spec))
            manifest["stageTwo"] = stage_two_manifest(result)
            manifest["decision"] = result["decision"]
            manifest["currentStage"] = "positive_thickness_3d_stack"
            manifest["geometryGenerated"] = bool(result["passed"])
            manifest["nextAuthorizedStage"] = (
                "erosion_onlap_lens_pinchout" if result["passed"] else None)
            if result["passed"]:
                model_payload = {"stack": result["stack"].to_dict(),
                                 "voxelization": result["voxelization"]}
        if args.event_spec:
            if not args.stack_spec:
                raise ValueError("--event-spec requires --stack-spec")
            result3 = run_stage_three(config, load_stack_spec(args.stack_spec),
                                      load_event_spec(args.event_spec))
            manifest["stageThree"] = stage_three_manifest(result3)
            manifest["decision"] = result3["decision"]
            manifest["currentStage"] = "erosion_onlap_lens_pinchout"
            manifest["geometryGenerated"] = bool(result3["passed"])
            manifest["nextAuthorizedStage"] = "compaction" if result3["passed"] else None
            if result3["passed"]:
                model_payload = {"eventModel": result3["eventModel"].to_dict(),
                                 "voxelization": result3["voxelization"]}
            else:
                model_payload = None
        if args.compaction_spec:
            if not args.stack_spec or not args.event_spec:
                raise ValueError("--compaction-spec requires --stack-spec and --event-spec")
            result4 = run_stage_four(config, load_stack_spec(args.stack_spec),
                                     load_event_spec(args.event_spec),
                                     load_compaction_spec(args.compaction_spec))
            manifest["stageFour"] = stage_four_manifest(result4)
            manifest["decision"] = result4["decision"]
            manifest["currentStage"] = "compaction"
            manifest["geometryGenerated"] = bool(result4["passed"])
            manifest["nextAuthorizedStage"] = (
                "fold_fault_kinematics" if result4["passed"] else None)
            if result4["passed"]:
                model_payload = {"compactedModel": result4["compactedModel"].to_dict(),
                                 "voxelization": result4["voxelization"]}
            else:
                model_payload = None
        if args.structural_spec:
            if not args.stack_spec or not args.event_spec or not args.compaction_spec:
                raise ValueError("--structural-spec requires all preceding stage specifications")
            result5 = run_stage_five(config, load_stack_spec(args.stack_spec),
                                     load_event_spec(args.event_spec),
                                     load_compaction_spec(args.compaction_spec),
                                     load_structural_spec(args.structural_spec))
            manifest["stageFive"] = stage_five_manifest(result5)
            manifest["decision"] = result5["decision"]
            manifest["currentStage"] = "fold_fault_kinematics"
            manifest["geometryGenerated"] = bool(result5["passed"])
            manifest["nextAuthorizedStage"] = (
                "intrusion_crosscutting" if result5["passed"] else None)
            model_payload = ({"structuralModel": result5["structuralModel"].to_dict()}
                             if result5["passed"] else None)
        if args.intrusion_spec:
            if not all((args.stack_spec, args.event_spec, args.compaction_spec,
                        args.structural_spec)):
                raise ValueError("--intrusion-spec requires all preceding stage specifications")
            result6 = run_stage_six(config, load_stack_spec(args.stack_spec),
                load_event_spec(args.event_spec), load_compaction_spec(args.compaction_spec),
                load_structural_spec(args.structural_spec), load_intrusion_spec(args.intrusion_spec))
            manifest["stageSix"] = stage_six_manifest(result6)
            manifest["decision"] = result6["decision"]
            manifest["currentStage"] = "intrusion_crosscutting"
            manifest["geometryGenerated"] = bool(result6["passed"])
            manifest["nextAuthorizedStage"] = "closed_mesh_and_brep" if result6["passed"] else None
            model_payload = ({"intrusionModel": result6["intrusionModel"].to_dict()}
                             if result6["passed"] else None)
        if args.mesh_spec:
            if not all((args.stack_spec,args.event_spec,args.compaction_spec,
                        args.structural_spec,args.intrusion_spec)):
                raise ValueError("--mesh-spec requires all preceding stage specifications")
            result7 = run_stage_seven(config,load_stack_spec(args.stack_spec),
                load_event_spec(args.event_spec),load_compaction_spec(args.compaction_spec),
                load_structural_spec(args.structural_spec),load_intrusion_spec(args.intrusion_spec),
                load_mesh_spec(args.mesh_spec))
            manifest["stageSeven"] = stage_seven_manifest(result7)
            manifest["decision"] = result7["decision"]
            manifest["currentStage"] = "closed_mesh_and_brep"
            manifest["geometryGenerated"] = bool(result7["passed"])
            manifest["nextAuthorizedStage"] = (
                "adaptive_refinement_and_boolean" if result7["passed"] else None)
            model_payload = ({"brepModel":result7["brepModel"].to_dict()}
                             if result7["passed"] else None)
        if args.refinement_spec:
            if not all((args.stack_spec,args.event_spec,args.compaction_spec,
                        args.structural_spec,args.intrusion_spec,args.mesh_spec)):
                raise ValueError("--refinement-spec requires all preceding stage specifications")
            result8=run_stage_eight(config,load_stack_spec(args.stack_spec),
              load_event_spec(args.event_spec),load_compaction_spec(args.compaction_spec),
              load_structural_spec(args.structural_spec),load_intrusion_spec(args.intrusion_spec),
              load_mesh_spec(args.mesh_spec),load_refinement_spec(args.refinement_spec))
            manifest["stageEight"]=stage_eight_manifest(result8)
            manifest["decision"]=result8["decision"]
            manifest["currentStage"]="adaptive_refinement_and_boolean"
            manifest["geometryGenerated"]=bool(result8["passed"])
            manifest["nextAuthorizedStage"]="uncertainty_ensemble" if result8["passed"] else None
            model_payload=({"adaptiveModel":result8["adaptiveModel"].to_dict()}
                           if result8["passed"] else None)
        if args.ensemble_spec:
            if not all((args.stack_spec,args.event_spec,args.compaction_spec,
                        args.structural_spec,args.intrusion_spec,args.mesh_spec,
                        args.refinement_spec)):
                raise ValueError("--ensemble-spec requires all preceding stage specifications")
            result9=run_stage_nine(config,load_stack_spec(args.stack_spec),
              load_event_spec(args.event_spec),load_compaction_spec(args.compaction_spec),
              load_structural_spec(args.structural_spec),load_intrusion_spec(args.intrusion_spec),
              load_mesh_spec(args.mesh_spec),load_refinement_spec(args.refinement_spec),
              load_ensemble_spec(args.ensemble_spec))
            manifest["stageNine"]=stage_nine_manifest(result9)
            manifest["decision"]=result9["decision"]
            manifest["currentStage"]="uncertainty_ensemble"
            manifest["geometryGenerated"]=bool(result9["passed"])
            manifest["nextAuthorizedStage"]="section_intersection" if result9["passed"] else None
            model_payload=({"ensemble":result9["ensemble"]} if result9["passed"] else None)
        if args.section_spec:
            if not all((args.stack_spec,args.event_spec,args.compaction_spec,args.structural_spec,
                        args.intrusion_spec,args.mesh_spec,args.refinement_spec,args.ensemble_spec)):
                raise ValueError("--section-spec requires all preceding stage specifications")
            result10=run_stage_ten(config,load_stack_spec(args.stack_spec),
              load_event_spec(args.event_spec),load_compaction_spec(args.compaction_spec),
              load_structural_spec(args.structural_spec),load_intrusion_spec(args.intrusion_spec),
              load_mesh_spec(args.mesh_spec),load_refinement_spec(args.refinement_spec),
              load_ensemble_spec(args.ensemble_spec),load_section_spec(args.section_spec))
            manifest["stageTen"]=stage_ten_manifest(result10)
            manifest["decision"]=result10["decision"]
            manifest["currentStage"]="section_intersection"
            manifest["geometryGenerated"]=bool(result10["passed"])
            manifest["nextAuthorizedStage"]="autocad_export_contract" if result10["passed"] else None
            model_payload=({"section":result10["section"]} if result10["passed"] else None)
        if args.export_spec:
            if not all((args.stack_spec,args.event_spec,args.compaction_spec,args.structural_spec,
                        args.intrusion_spec,args.mesh_spec,args.refinement_spec,args.ensemble_spec,
                        args.section_spec)):
                raise ValueError("--export-spec requires all preceding stage specifications")
            result11=run_stage_eleven(config,load_stack_spec(args.stack_spec),
              load_event_spec(args.event_spec),load_compaction_spec(args.compaction_spec),
              load_structural_spec(args.structural_spec),load_intrusion_spec(args.intrusion_spec),
              load_mesh_spec(args.mesh_spec),load_refinement_spec(args.refinement_spec),
              load_ensemble_spec(args.ensemble_spec),load_section_spec(args.section_spec),
              load_export_spec(args.export_spec))
            manifest["stageEleven"]=stage_eleven_manifest(result11)
            manifest["decision"]=result11["decision"]
            manifest["currentStage"]="autocad_export_contract"
            manifest["geometryGenerated"]=bool(result11["passed"])
            manifest["nextAuthorizedStage"]="native_dwg_writer_execution" if result11["passed"] else None
            model_payload=({"geologicContractEnvelope":result11["contractEnvelope"]}
                           if result11["passed"] else None)
        if args.release_spec:
            if not args.dwg_validation:
                raise ValueError("--release-spec requires --dwg-validation")
            release_result=run_stage_twelve(load_release_spec(args.release_spec),
                json.loads(args.dwg_validation.read_text(encoding="utf-8")))
            manifest["stageTwelve"]=stage_twelve_manifest(release_result)
            manifest["decision"]=release_result["decision"]
            manifest["currentStage"]="release_validation"
            manifest["nextAuthorizedStage"]=None
            model_payload={"releaseValidation":release_result["releaseValidation"]} if release_result["passed"] else None
    except Exception as error:
        print(json.dumps({"passed": False, "decision": "Rejected",
                          "error": str(error)}, ensure_ascii=False, indent=2))
        return 2
    payload = json.dumps(manifest, ensure_ascii=False, indent=2)
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(payload + "\n", encoding="utf-8")
    if args.model:
        if model_payload is None:
            raise ValueError("--model requires a successful geometry-stage run")
        args.model.parent.mkdir(parents=True, exist_ok=True)
        args.model.write_text(json.dumps(model_payload, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    print(payload)
    overall_passed = validation["passed"] and (not args.stack_spec or
        manifest["stageTwo"]["passed"]) and (not args.event_spec or
        manifest["stageThree"]["passed"])
    overall_passed = overall_passed and (not args.compaction_spec or
        manifest["stageFour"]["passed"])
    overall_passed = overall_passed and (not args.structural_spec or
        manifest["stageFive"]["passed"])
    overall_passed = overall_passed and (not args.intrusion_spec or
        manifest["stageSix"]["passed"])
    overall_passed = overall_passed and (not args.mesh_spec or
        manifest["stageSeven"]["passed"])
    overall_passed = overall_passed and (not args.refinement_spec or
        manifest["stageEight"]["passed"])
    overall_passed = overall_passed and (not args.ensemble_spec or
        manifest["stageNine"]["passed"])
    overall_passed = overall_passed and (not args.section_spec or
        manifest["stageTen"]["passed"])
    overall_passed = overall_passed and (not args.export_spec or
        manifest["stageEleven"]["passed"])
    overall_passed = overall_passed and (not args.release_spec or
        manifest["stageTwelve"]["passed"])
    return 0 if overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
