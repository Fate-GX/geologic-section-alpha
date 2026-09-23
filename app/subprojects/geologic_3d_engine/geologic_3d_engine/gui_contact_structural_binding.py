"""File backend for explicit structural-observation/contact binding review."""
import json
from pathlib import Path

from .section.contact_structural_binding import (accept_unique_contact_bindings,
    propose_contact_structural_bindings)


def execute_contact_structural_binding(plan_path,intersections_path,template_path,
                                       projected_path,output_parent,maximum_station_separation_m,
                                       accept_unique=False):
    paths=[Path(x).resolve() for x in (plan_path,intersections_path,template_path,projected_path)]
    plan,intersections,template,projected=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
    proposals=propose_contact_structural_bindings(plan.get("routeLonLat"),intersections,template,
        projected,maximum_station_separation_m)
    output=Path(output_parent).resolve()/"contact_structural_binding";output.mkdir(parents=True,exist_ok=True)
    proposal_path=output/"contact_structural_binding_proposals.json"
    proposal_path.write_text(json.dumps(proposals,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    accepted_path=None
    if accept_unique:
        ids=[x["hypothesisId"] for x in proposals["proposals"] if x["status"]=="UniqueCandidate"]
        accepted=accept_unique_contact_bindings(template,proposals,ids)
        accepted_path=output/"contact_orientation_evidence_candidates.json"
        accepted_path.write_text(json.dumps(accepted,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return proposals,proposal_path,accepted_path
