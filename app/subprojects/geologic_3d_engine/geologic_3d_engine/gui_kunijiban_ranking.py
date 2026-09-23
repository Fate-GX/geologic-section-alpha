"""GUI backend for bounded, screening-only KuniJiban metadata ranking."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

from .evidence.kunijiban_bed0300 import RECORD_URL
from .evidence.kunijiban_candidate_metadata import build_ranked_candidate_metadata


def _fetch(identifier, timeout):
    request=urllib.request.Request(RECORD_URL.format(record_id=identifier),headers={
        "User-Agent":"geologic-3d-engine-research/1.0"})
    with urllib.request.urlopen(request,timeout=timeout) as response:
        return identifier,response.read()


def execute_kunijiban_candidate_ranking(candidate_index_path, output_parent,
                                         *, workers=3, timeout=30):
    source=Path(candidate_index_path).resolve()
    index=json.loads(source.read_text(encoding="utf-8"))
    candidates=index.get("candidates") if isinstance(index,dict) else None
    if not isinstance(candidates,list) or not 1<=len(candidates)<=50:
        raise ValueError("候補数は1～50件である必要があります。")
    if isinstance(workers,bool) or not isinstance(workers,int) or not 1<=workers<=4:
        raise ValueError("同時取得数は1～4である必要があります。")
    identifiers=[int(row["providerRecordId"]) for row in candidates]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        responses=list(pool.map(lambda value:_fetch(value,timeout),identifiers))
    result=build_ranked_candidate_metadata(index,responses)
    result["candidateIndexArtifactSha256"]=hashlib.sha256(source.read_bytes()).hexdigest()
    unsigned={key:value for key,value in result.items() if key!="recordSha256"}
    result["recordSha256"]=hashlib.sha256(json.dumps(unsigned,sort_keys=True,
        separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    output=Path(output_parent).resolve()/"kunijiban_candidates"
    output.mkdir(parents=True,exist_ok=True)
    target=output/"route_borehole_candidates_ranked.json"
    temporary=target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temporary.replace(target)
    return result,target


def candidate_table_rows(ranked):
    """Return display-only rows without changing the evidence decision."""
    if not isinstance(ranked,dict) or ranked.get("schemaVersion")!="KuniJibanRankedCandidateMetadata-1.0":
        raise ValueError("順位付き候補JSONの形式が不正です。")
    claimed=ranked.get("recordSha256")
    unsigned={key:value for key,value in ranked.items() if key!="recordSha256"}
    actual=hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),
        ensure_ascii=False).encode()).hexdigest()
    if claimed!=actual:
        raise ValueError("順位付き候補JSONのハッシュが一致しません。")
    rows=[]
    for candidate in ranked.get("candidates",[]):
        metadata=candidate["xmlMetadata"]
        rows.append({
            "providerRecordId":candidate["providerRecordId"],
            "distanceM":float(candidate["projectionDistanceM"]),
            "boreholeName":metadata.get("boreholeName") or "(名称なし)",
            "dtdVersion":metadata.get("dtdVersion") or metadata.get("detectedDtdVersion"),
            "coordinateMethod":metadata["coordinateMethodClass"],
            "resolutionArcSeconds":metadata.get("declaredResolutionArcSeconds"),
            "horizontalCrs":metadata.get("formatHorizontalCrs","Unresolved"),
            "totalDepthM":float(metadata.get("totalDepthM",0.0)),
            "providerApprovalLabel":candidate.get("providerApprovalLabel"),
            "sectionConstraintAuthorized":False,
        })
    return rows
