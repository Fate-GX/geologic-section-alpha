"""GUI backend for an explicit mapped-contact orientation input template."""
import json
from pathlib import Path

from .section.contact_orientation_hypothesis import (
    build_contact_orientation_hypothesis_template)


def execute_contact_orientation_template(intersections_path, output_parent):
    source=Path(intersections_path).resolve()
    document=json.loads(source.read_text(encoding="utf-8"))
    result=build_contact_orientation_hypothesis_template(document)
    output=Path(output_parent).resolve()/"contact_orientation_hypotheses"
    output.mkdir(parents=True,exist_ok=True)
    target=output/"contact_orientation_hypothesis_template.json"
    temporary=target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temporary.replace(target)
    return result,target
