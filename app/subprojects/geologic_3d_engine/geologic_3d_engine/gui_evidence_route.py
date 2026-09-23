"""Backend for an explicitly selected evidence-aware route proposal."""
from __future__ import annotations
import json
from pathlib import Path
from .section.evidence_aware_route import build_evidence_aware_route_candidate


def execute_evidence_route_candidate(route_conditions, borehole_path, output_directory):
    document=json.loads(Path(borehole_path).read_text(encoding="utf-8"))
    if document.get("schemaVersion")!="PublicBoreholeEvidence-1.0":
        raise ValueError("PublicBoreholeEvidence-1.0 is required")
    holes=document.get("boreholes")
    if not isinstance(holes,list) or len(holes)!=1:
        raise ValueError("select a normalized file containing exactly one borehole")
    result=build_evidence_aware_route_candidate(route_conditions.vertices,holes[0])
    output=Path(output_directory)/"evidence_route_candidates"
    output.mkdir(parents=True,exist_ok=True)
    target=output/f"{result['boreholeId']}_route_candidate.json"
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result,target
