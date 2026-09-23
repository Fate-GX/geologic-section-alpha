"""GUI backend for a plan-bound KuniJiban candidate XML capture."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from .evidence.kunijiban_bed0300 import capture_and_normalize_record
from .section.borehole_evidence import screen_boreholes_to_geographic_route


def _canonical_hash(document):
    unsigned = {key: value for key, value in document.items() if key != "recordSha256"}
    return hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def execute_kunijiban_record_capture(plan_path, candidate_index_path, record_id,
                                     output_parent):
    plan_source = Path(plan_path).resolve()
    index_source = Path(candidate_index_path).resolve()
    plan = json.loads(plan_source.read_text(encoding="utf-8"))
    index = json.loads(index_source.read_text(encoding="utf-8"))
    if plan.get("schemaVersion") != "PlanEvidenceBundle-1.0":
        raise ValueError("PlanEvidenceBundle-1.0が必要です。")
    if index.get("schemaVersion") != "KuniJibanRouteCandidateIndex-1.0":
        raise ValueError("KuniJiban候補一覧の形式が不正です。")
    if index.get("recordSha256") != _canonical_hash(index):
        raise ValueError("KuniJiban候補一覧のハッシュが一致しません。")
    plan_hash = hashlib.sha256(plan_source.read_bytes()).hexdigest()
    if index.get("planEvidenceSha256") != plan_hash:
        raise ValueError("候補一覧は選択された測線証拠に結合されていません。")
    matches = [row for row in index.get("candidates", [])
               if row.get("providerRecordId") == int(record_id)]
    if len(matches) != 1:
        raise ValueError("指定IDは候補一覧に一意に存在しません。")
    marker = matches[0]
    output = Path(output_parent).resolve() / "kunijiban_records" / str(int(record_id))
    result, xml_path, json_path = capture_and_normalize_record(
        record_id, output, provider_approval_label=marker.get("providerApprovalLabel"))
    screening = screen_boreholes_to_geographic_route(
        [result], plan["routeLonLat"],
        coordinate_assumption="BED0300Code1_JGD2000_ScreenOnly_NoJGD2011Transform")
    result.update({
        "candidateIndexArtifactSha256": hashlib.sha256(index_source.read_bytes()).hexdigest(),
        "planEvidenceSha256": plan_hash,
        "routeScreening": screening[0],
        "routeConstraintDecision": "Rejected_TransformAndIndividualAccuracyUnverified",
    })
    result["recordSha256"] = _canonical_hash(result)
    temporary = json_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(json_path)
    collection={
        "schemaVersion":"NormalizedBoreholeEvidenceCollection-1.0",
        "source":"KuniJibanSelectedRecord",
        "candidateArtifactSha256":hashlib.sha256(json_path.read_bytes()).hexdigest(),
        "boreholes":[result],
        "correlationState":"NotCorrelated",
        "sectionConstraintAuthorized":False,
    }
    collection_path=output/f"kunijiban_{int(record_id)}_borehole_collection.json"
    collection_tmp=collection_path.with_suffix(".json.tmp")
    collection_tmp.write_text(json.dumps(collection,ensure_ascii=False,indent=2)+"\n",
                              encoding="utf-8")
    collection_tmp.replace(collection_path)
    return result, xml_path, json_path, collection_path
