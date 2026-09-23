"""GUI-safe writer for arbitrary-route evidence-readiness records."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .section.route_evidence_readiness import assess_route_evidence_readiness
from .section.borehole_correlation import validate_correlation_review
from .section.route_evidence_workspace import assemble_route_evidence_workspace
from .section.route_evidence_workspace_render import render_route_evidence_workspace


def _load(path):
    value=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value,dict):raise ValueError("evidence artifact must be a JSON object")
    return value


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def execute_route_readiness(plan_path, output_directory, borehole_intake_path=None,
                            structural_observations_path=None,
                            mapped_crossings_path=None,
                            contact_plane_diagnostics_path=None,
                            correlation_review_path=None):
    plan=_load(plan_path)
    boreholes=[];intake=None;hashes={"planEvidence":_sha(plan_path)}
    if borehole_intake_path:
        intake=_load(borehole_intake_path)
        if intake.get("schemaVersion")!="BoreholeSectionIntake-1.0":
            raise ValueError("BoreholeSectionIntake-1.0 is required")
        boreholes=intake.get("boreholes",[])
        hashes["boreholeIntake"]=_sha(borehole_intake_path)
    structural=[]
    if structural_observations_path:
        document=_load(structural_observations_path)
        if document.get("schemaVersion")!="StructuralObservationProjection-1.0":
            raise ValueError("StructuralObservationProjection-1.0 is required")
        structural=document.get("observations",[])
        hashes["structuralObservations"]=_sha(structural_observations_path)
    crossings=None
    if mapped_crossings_path:
        crossings=_load(mapped_crossings_path)
        hashes["mappedCrossings"]=_sha(mapped_crossings_path)
    planes=None
    if contact_plane_diagnostics_path:
        planes=_load(contact_plane_diagnostics_path)
        hashes["contactPlaneDiagnostics"]=_sha(contact_plane_diagnostics_path)
    reviewed=[]
    if correlation_review_path:
        if intake is None:
            raise ValueError("a correlation review requires its borehole intake")
        review=_load(correlation_review_path)
        validate_correlation_review(intake,review)
        hashes["correlationReview"]=_sha(correlation_review_path)
        reviewed=[{"reviewStatus":"Accepted","artifactBound":True,
                   "reviewType":"GeologistInterpretedBoreholeCorrelation"}]
    result=assess_route_evidence_readiness(
        plan,mapped_crossings=crossings,boreholes=boreholes,
        structural_observations=structural,contact_plane_diagnostics=planes,
        reviewed_geometry=reviewed,input_artifact_sha256=hashes)
    output=Path(output_directory).resolve();output.mkdir(parents=True,exist_ok=True)
    target=output/"route_evidence_readiness.json"
    temporary=target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temporary.replace(target)
    return result,target


def execute_route_evidence_workspace(plan_path, output_directory,
                                     borehole_intake_path=None,
                                     structural_observations_path=None):
    """Write one route-bound evidence overlay artifact for later section work."""
    result = assemble_route_evidence_workspace(
        plan_path, borehole_path=borehole_intake_path,
        structural_path=structural_observations_path)
    output=Path(output_directory).resolve();output.mkdir(parents=True,exist_ok=True)
    target=output/"route_evidence_workspace.json"
    temporary=target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temporary.replace(target)
    image=output/"route_evidence_section.png"
    render=render_route_evidence_workspace(target,image)
    (output/"route_evidence_section_render.json").write_text(
        json.dumps(render,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result,target
