"""Validate reviewed correlation and issue a section JSON plus PNG."""
import json
from pathlib import Path

from .section.borehole_correlation import build_reviewed_borehole_section
from .section.borehole_section_render import render_borehole_section
from .section.structural_observations import audit_section_apparent_dips
from .section.geographic_linework import audit_mapped_contacts
from .section.section_faults import apply_vertical_throw
from .section.section_unconformity import apply_erosion_fill


def execute_reviewed_section(plan_path,intake_path,review_path,output_parent,structural_path=None,linework_path=None,fault_evidence_path=None,erosion_fill_path=None,qualitative_stratigraphy_path=None):
    plan=json.loads(Path(plan_path).read_text(encoding="utf-8"))
    intake=json.loads(Path(intake_path).read_text(encoding="utf-8"))
    review=json.loads(Path(review_path).read_text(encoding="utf-8"))
    qualitative=None
    if qualitative_stratigraphy_path:
        from .section.qualitative_stratigraphic_constraints import (
            load_qualitative_stratigraphic_constraints)
        qualitative=load_qualitative_stratigraphic_constraints(qualitative_stratigraphy_path)
    section=build_reviewed_borehole_section(plan,intake,review,qualitative)
    if erosion_fill_path:
        erosion=json.loads(Path(erosion_fill_path).read_text(encoding="utf-8"))
        section=apply_erosion_fill(section,erosion)
    linework=None
    if linework_path:
        linework=json.loads(Path(linework_path).read_text(encoding="utf-8"))
        if fault_evidence_path:
            evidence=json.loads(Path(fault_evidence_path).read_text(encoding="utf-8"))
            records=evidence.get("faultEvidence") if isinstance(evidence,dict) else None
            if not isinstance(records,list) or not records:raise ValueError("faultEvidence配列を1件以上含むJSONが必要です。")
            events={v["featureId"]:v for v in linework["events"] if v["kind"]=="Fault"}
            for record in records:
                if record.get("faultId") not in events:raise ValueError("変位証拠に対応する測線断層交差がありません。")
                section=apply_vertical_throw(section,events[record["faultId"]],record)
        audit=audit_mapped_contacts(section,linework)
        section["mappedContactAudit"]=audit
        if audit["applicability"]=="Applicable":
            section["validation"]["mappedContactCompatibility"]=audit["passed"]
    elif fault_evidence_path:
        raise ValueError("断層変位には地質図線交差結果が必要です。")
    if structural_path:
        structural=json.loads(Path(structural_path).read_text(encoding="utf-8"))
        audit=audit_section_apparent_dips(section,structural["observations"])
        section["structuralOrientationAudit"]=audit
        section["validation"]["structuralOrientationCompatibility"]=audit["passed"]
    output=Path(output_parent).resolve()/"reviewed_borehole_section";output.mkdir(parents=True,exist_ok=True)
    json_path=output/"interpreted_section.json"
    json_path.write_text(json.dumps(section,ensure_ascii=False,indent=2),encoding="utf-8")
    image_path=output/"interpreted_section.png"
    render_borehole_section(section,intake,image_path,linework=linework)
    return section,json_path,image_path
