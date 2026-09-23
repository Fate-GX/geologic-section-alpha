"""Stage-11 neutral AutoCAD export-contract orchestration."""

from . import __version__
from .export.autocad_contract import build_autocad_contract
from .export.contract_integrity import build_integrity_envelope
from .runner import configuration_fingerprint
from .stage10 import run_stage_ten


def _lineage_manifest(config, stage10, ensemble_spec):
    config_data=config.to_dict()
    affected={item.unit_id:[] for item in config.units}
    for event in config.events:
        for unit_id in event.affected_unit_ids:
            affected.setdefault(unit_id,[]).append(event.event_id)
    return {"lineageVersion":"1.0","regionalProfileId":config.regional_profile_id,
      "configurationSha256":configuration_fingerprint(config),
      "sources":config_data["sources"],"events":config_data["events"],
      "relations":config_data["relations"],
      "unitLineage":[{"unitId":item.unit_id,"sourceIds":list(item.source_ids),
        "eventIds":affected.get(item.unit_id,[]),"normalizedLithology":item.normalized_lithology,
        "termStatus":item.term_status} for item in config.units],
      "stagePath":[f"Stage{index}" for index in range(1,12)],
      "uncertainty":{"projection":stage10["modelSummary"]["uncertaintyProjection"],
        "evidenceSourceIds":sorted({source_id for item in ensemble_spec.parameter_ranges
                                     for source_id in item.evidence_source_ids})}}


def run_stage_eleven(config,stack_spec,event_spec,compaction_spec,structural_spec,
                     intrusion_spec,mesh_spec,refinement_spec,ensemble_spec,section_spec,export_spec):
    stage10=run_stage_ten(config,stack_spec,event_spec,compaction_spec,structural_spec,
      intrusion_spec,mesh_spec,refinement_spec,ensemble_spec,section_spec)
    if not stage10["passed"]:
        return {"passed":False,"decision":"Rejected","stage":"autocad_export_contract",
                "errors":[{"code":"BlockedByStageTen"}],"stageTen":stage10}
    try:
        contract=build_autocad_contract(stage10["section"],export_spec,__version__,
                                        stage10["uncertaintySection"])
        contract["lineageManifest"]=_lineage_manifest(config,stage10,ensemble_spec)
        payload={key:value for key,value in contract.items()
                 if key not in {"contractSha256","validation"}}
        envelope=build_integrity_envelope(payload,contract["validation"],__version__)
    except Exception as error:
        return {"passed":False,"decision":"Rejected","stage":"autocad_export_contract",
          "errors":[{"code":"ExportContractFailed","message":str(error)}],"stageTen":stage10}
    gate={"passed":contract["validation"]["passed"],"gate":"NeutralAutoCadExportContract",
      "errors":[],**contract["validation"],"contractSha256":contract["contractSha256"],
      "nativeDwgWritten":False,"nativeDwgReopenValidated":False}
    return {"passed":gate["passed"],"decision":"Experimental","stage":"autocad_export_contract",
      "stageTen":stage10,"gates":[gate],"contract":contract,"contractEnvelope":envelope,
      "modelSummary":{"polygonCount":gate["polygonCount"],"contractVersion":contract["contractVersion"],
        "contractSha256":contract["contractSha256"],"nativeDwgStatus":"PendingWriterExecution"}}


def stage_eleven_manifest(result):
    return {"stage":result["stage"],"passed":result["passed"],"decision":result["decision"],
      "errors":result.get("errors",[]),"gates":result.get("gates",[]),
      "modelSummary":result.get("modelSummary"),"geometryGenerated":bool(result["passed"]),
      "geometryType":"NeutralAutoCadSectionContract" if result["passed"] else None,
      "nextAuthorizedStage":"native_dwg_writer_execution" if result["passed"] else None}
