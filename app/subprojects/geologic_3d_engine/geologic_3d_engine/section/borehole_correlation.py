"""Convert only an explicit, artifact-bound borehole correlation into surfaces."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Mapping

from .evidence_section_workflow import build_evidence_constrained_section


def canonical_sha256(value):
    encoded=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_correlation_review(intake: Mapping, review: Mapping):
    required={"schemaVersion","correlationId","reviewer","reviewedAt",
              "intakeSha256","unitsBottomUp","reviewStatus"}
    if not isinstance(review,Mapping) or not required.issubset(review):
        raise ValueError("correlation review is incomplete")
    if review["schemaVersion"]!="BoreholeCorrelationReview-1.0" or review["reviewStatus"]!="GeologistInterpreted":
        raise ValueError("an explicit GeologistInterpreted correlation review is required")
    if not all(isinstance(review[k],str) and review[k].strip()
               for k in ("correlationId","reviewer","reviewedAt")):
        raise ValueError("correlation identity, reviewer and review time are required")
    if review["intakeSha256"]!=canonical_sha256(intake):
        raise ValueError("correlation review is not bound to this intake artifact")
    holes={row["boreholeId"]:row for row in intake.get("boreholes",[])
           if row.get("projectionState")=="Projected"}
    if len(holes)<3:raise ValueError("at least three projected boreholes are required")
    units=review["unitsBottomUp"]
    if not isinstance(units,list) or not units:raise ValueError("correlated units are required")
    seen_units=set();used={key:[] for key in holes};prepared=[]
    for unit in units:
        if not isinstance(unit,Mapping) or set(unit)!={"unitId","normalizedLithology","members"}:
            raise ValueError("invalid correlated unit")
        if not unit["unitId"] or unit["unitId"] in seen_units:
            raise ValueError("unit IDs must be non-empty and unique")
        seen_units.add(unit["unitId"]);members=unit["members"]
        if not isinstance(members,list) or len(members)<3:
            raise ValueError("each unit requires at least three borehole members")
        seen_holes=set();samples=[]
        for member in members:
            if not isinstance(member,Mapping) or set(member)!={"boreholeId","intervalIndex"}:
                raise ValueError("invalid correlation member")
            hole_id,index=member["boreholeId"],member["intervalIndex"]
            if hole_id not in holes or hole_id in seen_holes or isinstance(index,bool) or not isinstance(index,int):
                raise ValueError("members must reference unique projected boreholes")
            intervals=holes[hole_id]["intervals"]
            if index<0 or index>=len(intervals):raise ValueError("interval index is invalid")
            interval=intervals[index]
            if interval["normalizedLithology"]!=unit["normalizedLithology"]:
                raise ValueError("review lithology disagrees with selected interval")
            seen_holes.add(hole_id);used[hole_id].append(index)
            lon,lat=holes[hole_id]["sourceLonLat"]
            samples.append({"longitude":lon,"latitude":lat,
              "trueThicknessM":interval["topElevationM"]-interval["bottomElevationM"],
              "sourceId":holes[hole_id]["sourceId"],"evidenceStatus":"Interpreted"})
        prepared.append({"unitId":unit["unitId"],"normalizedLithology":unit["normalizedLithology"],
                         "thicknessEvidence":samples})
    for indexes in used.values():
        if indexes and indexes!=list(range(max(indexes),min(indexes)-1,-1)):
            raise ValueError("selected intervals must be consecutive in bottom-up order")
    reference=[]
    for member in units[0]["members"]:
        hole=holes[member["boreholeId"]];interval=hole["intervals"][member["intervalIndex"]]
        lon,lat=hole["sourceLonLat"]
        reference.append({"longitude":lon,"latitude":lat,"elevationM":interval["bottomElevationM"],
                          "sourceId":hole["sourceId"],"evidenceStatus":"Interpreted"})
    return {"referenceObservations":reference,"units":prepared,
            "correlationId":review["correlationId"],"reviewer":review["reviewer"],
            "authorization":"InterpretedHypothesis_NotIndependentEvidenceAuthorization"}


def build_reviewed_borehole_section(plan_bundle, intake, review,
                                    qualitative_constraints=None):
    prepared=validate_correlation_review(intake,review)
    plan=dict(plan_bundle);plan["authorizationState"]="SubsurfaceInterpretationInputsPresent"
    result=build_evidence_constrained_section(plan,prepared["referenceObservations"],prepared["units"],
                                               qualitative_constraints=qualitative_constraints)
    result["correlation"]={k:prepared[k] for k in ("correlationId","reviewer","authorization")}
    return result


def build_correlation_review_template(intake):
    candidates=[]
    for hole in intake.get("boreholes",[]):
        if hole.get("projectionState")!="Projected":continue
        candidates.append({"boreholeId":hole["boreholeId"],"stationM":hole["stationM"],
          "projectionDistanceM":hole["projectionDistanceM"],
          "intervals":[{"intervalIndex":v["intervalIndex"],"sourceLabel":v["sourceLabel"],
                        "normalizedLithology":v["normalizedLithology"],
                        "topElevationM":v["topElevationM"],"bottomElevationM":v["bottomElevationM"]}
                       for v in hole["intervals"]]})
    return {"schemaVersion":"BoreholeCorrelationReview-1.0","correlationId":"",
      "reviewer":"","reviewedAt":"","intakeSha256":canonical_sha256(intake),
      "reviewStatus":"Draft_NotReviewed","unitsBottomUp":[],
      "candidateIntervals":candidates,
      "instructions":"Copy selected boreholeId/intervalIndex pairs into unitsBottomUp; do not infer correlation from equal labels alone."}


def create_correlation_review(intake, correlation_id, reviewer, units_bottom_up,
                              reviewed_at=None):
    """Create and validate a review from explicit UI selections."""
    if not isinstance(correlation_id,str) or not correlation_id.strip():
        raise ValueError("correlation ID is required")
    if not isinstance(reviewer,str) or not reviewer.strip():
        raise ValueError("reviewer is required")
    review={"schemaVersion":"BoreholeCorrelationReview-1.0",
      "correlationId":correlation_id.strip(),"reviewer":reviewer.strip(),
      "reviewedAt":reviewed_at or datetime.now(timezone.utc).isoformat(),
      "intakeSha256":canonical_sha256(intake),"reviewStatus":"GeologistInterpreted",
      "unitsBottomUp":units_bottom_up}
    validate_correlation_review(intake,review)
    return review
