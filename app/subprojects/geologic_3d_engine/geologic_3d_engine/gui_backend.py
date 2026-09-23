"""Headless backend shared by the simple GUI and independent validation."""

from __future__ import annotations

import json
from pathlib import Path

from .config import load_config
from .events.event_spec import load_event_spec
from .events.intrusion_spec import load_intrusion_spec
from .export.export_spec import load_export_spec
from .geometry.mesh_spec import load_mesh_spec
from .geometry.refinement_spec import load_refinement_spec
from .physics.compaction_spec import load_compaction_spec
from .physics.structural_spec import load_structural_spec
from .section.section_spec import load_section_spec
from .stage11 import run_stage_eleven,stage_eleven_manifest
from .stratigraphy.stack_spec import load_stack_spec
from .uncertainty.ensemble_spec import load_ensemble_spec

REQUIRED_INPUTS=("config","stackSpec","eventSpec","compactionSpec","structuralSpec",
                 "intrusionSpec","meshSpec","refinementSpec","ensembleSpec","sectionSpec",
                 "exportSpec")


def load_run_bundle(path):
    bundle_path=Path(path).resolve()
    data=json.loads(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or data.get("bundleVersion")!="1.0":
        raise ValueError("bundleVersion 1.0 is required")
    if data.get("targetStage")!="Stage11NeutralContract":
        raise ValueError("only Stage11NeutralContract is supported")
    inputs=data.get("inputs")
    if not isinstance(inputs,dict) or set(inputs)!=set(REQUIRED_INPUTS):
        raise ValueError("inputs must contain exactly the required Stage-11 paths")
    resolved={key:_resolve_portable(bundle_path.parent,value) for key,value in inputs.items()}
    return data,resolved


def execute_run_bundle(bundle_path,output_directory):
    data,paths=load_run_bundle(bundle_path)
    output=Path(output_directory).resolve();output.mkdir(parents=True,exist_ok=True)
    result=run_stage_eleven(load_config(paths["config"]),load_stack_spec(paths["stackSpec"]),
      load_event_spec(paths["eventSpec"]),load_compaction_spec(paths["compactionSpec"]),
      load_structural_spec(paths["structuralSpec"]),load_intrusion_spec(paths["intrusionSpec"]),
      load_mesh_spec(paths["meshSpec"]),load_refinement_spec(paths["refinementSpec"]),
      load_ensemble_spec(paths["ensembleSpec"]),load_section_spec(paths["sectionSpec"]),
      load_export_spec(paths["exportSpec"]))
    summary={"passed":result["passed"],"decision":result["decision"],
      "targetStage":data["targetStage"],"syntheticDisclosure":
      "Synthetic geological hypothesis / 疑似地質モデル",
      "contractWritten":bool(result["passed"]),"errors":result.get("errors",[])}
    _write_json(output/"run_summary.json",summary)
    _write_json(output/"stage11_manifest.json",stage_eleven_manifest(result))
    if result["passed"]:
        _write_json(output/"contract_envelope.json",result["contractEnvelope"])
        _write_json(output/"neutral_contract.json",result["contract"])
    else:
        _remove_stale_success_artifact(output/"contract_envelope.json")
        _remove_stale_success_artifact(output/"neutral_contract.json")
    return result


def _resolve_portable(base,value):
    if not isinstance(value,str) or not value or Path(value).is_absolute():
        raise ValueError("bundle input paths must be non-empty relative paths")
    root=base.resolve();candidate=(root/value).resolve()
    if root!=candidate and root not in candidate.parents:
        raise ValueError("bundle input path escapes the bundle directory")
    if not candidate.is_file():raise ValueError(f"bundle input file does not exist: {value}")
    return candidate


def _write_json(path,value):
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temporary.replace(path)


def _remove_stale_success_artifact(path):
    if path.exists():
        if not path.is_file():raise ValueError(f"expected output artifact is not a file: {path.name}")
        path.unlink()
