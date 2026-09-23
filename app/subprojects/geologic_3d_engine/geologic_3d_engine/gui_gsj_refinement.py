"""GUI backend for source-bound adaptive GSJ transition refinement."""
import json
from pathlib import Path
import urllib.parse
import urllib.request

from .section.gsj_adaptive_transition import (
    apply_transition_refinement, refine_surface_transition)
from .section.gsj_surface_geology import GSJ_LEGEND_URL


def _official_query(latitude, longitude):
    query = urllib.parse.urlencode({"point": f"{latitude:.10f},{longitude:.10f}",
                                   "type": "level4"})
    request = urllib.request.Request(f"{GSJ_LEGEND_URL}?{query}",
        headers={"User-Agent": "geologic-3d-engine-research/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def execute_gsj_refinement(plan_path, transition_index, target_width_m,
                           output_parent, query_point=None, maximum_queries=20):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    refinement = refine_surface_transition(plan, transition_index,
        query_point or _official_query, target_width_m, maximum_queries)
    output = Path(output_parent).resolve()/"gsj_transition_refinement"
    output.mkdir(parents=True, exist_ok=True)
    artifact = output/"gsj_transition_refinement.json"
    artifact.write_text(json.dumps(refinement, ensure_ascii=False, indent=2), encoding="utf-8")
    refined_plan = None
    review_template = None
    if refinement["reviewEligibility"] == "Eligible":
        from .section.gsj_transition_review import build_transition_review_template
        updated = apply_transition_refinement(plan, refinement)
        refined_plan = output/"refined_plan_evidence_bundle.json"
        refined_plan.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
        review_template = output/"surface_transition_review_template.json"
        review_template.write_text(json.dumps(build_transition_review_template(updated),
                                               ensure_ascii=False, indent=2), encoding="utf-8")
    return refinement, artifact, refined_plan, review_template
