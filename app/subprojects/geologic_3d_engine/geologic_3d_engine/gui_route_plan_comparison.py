"""File-bound backend for original/candidate route-plan comparison."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .section.route_plan_comparison import compare_route_plan_evidence


def execute_route_plan_comparison(original_plan_path, candidate_plan_path,
                                  route_proposal_path, output_parent,
                                  maximum_direction_change_degrees=120.0):
    paths = [Path(p).resolve() for p in
             (original_plan_path, candidate_plan_path, route_proposal_path)]
    values = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    result = compare_route_plan_evidence(
        *values, maximum_direction_change_degrees=maximum_direction_change_degrees)
    result["inputArtifactSha256"] = {
        "originalPlan": hashlib.sha256(paths[0].read_bytes()).hexdigest(),
        "candidatePlan": hashlib.sha256(paths[1].read_bytes()).hexdigest(),
        "routeProposal": hashlib.sha256(paths[2].read_bytes()).hexdigest()}
    output = Path(output_parent).resolve()/"route_plan_comparison"
    output.mkdir(parents=True, exist_ok=True)
    target = output/"route_plan_evidence_comparison.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    temporary.replace(target)
    return result, target
