"""GUI backend for immutable borehole intake and route projection."""
import json
from pathlib import Path

from .section.borehole_section_intake import load_and_project_borehole_file
from .section.borehole_correlation import build_correlation_review_template


def execute_borehole_intake(source_path, output_parent, route_conditions, maximum_offset_m):
    result=load_and_project_borehole_file(source_path,route_conditions.vertices,maximum_offset_m)
    output=Path(output_parent).resolve()/"borehole_section_intake"
    output.mkdir(parents=True,exist_ok=True)
    target=output/"projected_boreholes.json"
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    template=output/"correlation_review_template.json"
    template.write_text(json.dumps(build_correlation_review_template(result),ensure_ascii=False,indent=2),encoding="utf-8")
    return result,target,template
