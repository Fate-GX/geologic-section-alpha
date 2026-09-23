"""Convert a reviewed GSJ transition bracket into contact-audit events."""
import json
from pathlib import Path
from .section.gsj_transition_review import validate_transition_review

def execute_gsj_transition_review(plan_path,review_path,output_parent):
    plan=json.loads(Path(plan_path).read_text(encoding="utf-8"));review=json.loads(Path(review_path).read_text(encoding="utf-8"))
    result=validate_transition_review(plan,review)
    output=Path(output_parent).resolve()/"gsj_transition_review";output.mkdir(parents=True,exist_ok=True)
    target=output/"reviewed_surface_contact_events.json";target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result,target
