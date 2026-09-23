"""GUI backend for exact mapped-contact review templates and conversion."""
import json
from pathlib import Path
from .section.mapped_contact_review import (build_mapped_contact_review_template,
    load_and_validate_mapped_contact_review)

def create_mapped_contact_review_template(adjacency_path,correlation_path,output_parent):
    correlation=json.loads(Path(correlation_path).read_text(encoding="utf-8"))
    result=build_mapped_contact_review_template(adjacency_path,correlation)
    output=Path(output_parent).resolve()/"mapped_contact_review";output.mkdir(parents=True,exist_ok=True)
    target=output/"mapped_contact_review_template.json"
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result,target

def execute_mapped_contact_review(adjacency_path,correlation_path,review_path,output_parent):
    result=load_and_validate_mapped_contact_review(adjacency_path,correlation_path,review_path)
    output=Path(output_parent).resolve()/"mapped_contact_review";output.mkdir(parents=True,exist_ok=True)
    target=output/"reviewed_exact_surface_contact_events.json"
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result,target
