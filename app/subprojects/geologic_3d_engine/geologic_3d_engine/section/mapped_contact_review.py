"""Bind exact mapped polygon transitions to reviewed section contacts."""
import hashlib,json
from pathlib import Path
from typing import Mapping

from .mapped_polygon_adjacency import load_mapped_polygon_adjacency

def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()

def _candidates(adjacency):
    rows=[]
    for crossing in adjacency["crossings"]:
        if crossing["sideClassificationStatus"]!="MappedUnitTransition":continue
        rows.append({"featureId":crossing["featureId"],"stationM":crossing["stationM"],
          "sourcePolygonFeatureIds":[v["sourcePolygonFeatureId"] for v in crossing["unitPair"]],
          "sourceUnits":crossing["unitPair"]})
    return rows

def build_mapped_contact_review_template(adjacency_path,correlation_review):
    adjacency=load_mapped_polygon_adjacency(adjacency_path)
    return {"schemaVersion":"MappedContactCorrelationReview-1.0",
      "adjacencyRecordSha256":adjacency["recordSha256"],
      "correlationReviewSha256":canonical_sha256(correlation_review),
      "reviewer":"","reviewedAt":"","reviewStatus":"Draft_NotReviewed",
      "candidates":_candidates(adjacency),"decisions":[],
      "instructions":"Decide every candidate as UseAsSectionContact or Exclude; a used contactIndex must separate the declared adjacent model units."}

def validate_mapped_contact_review(adjacency,correlation_review,review):
    required={"schemaVersion","adjacencyRecordSha256","correlationReviewSha256",
      "reviewer","reviewedAt","reviewStatus","candidates","decisions"}
    if not isinstance(review,Mapping) or not required.issubset(review):raise ValueError("mapped contact review is incomplete")
    if review["schemaVersion"]!="MappedContactCorrelationReview-1.0" or review["reviewStatus"]!="GeologistInterpreted":
        raise ValueError("mapped contact review must be explicitly GeologistInterpreted")
    if review["adjacencyRecordSha256"]!=adjacency["recordSha256"] or review["correlationReviewSha256"]!=canonical_sha256(correlation_review):
        raise ValueError("mapped contact review is not bound to its evidence and correlation")
    if not review["reviewer"] or not review["reviewedAt"]:raise ValueError("mapped contact reviewer and time are required")
    expected={v["featureId"]:v for v in _candidates(adjacency)}
    if review["candidates"]!=list(expected.values()):raise ValueError("mapped contact candidate snapshot changed")
    decisions=review["decisions"]
    if not isinstance(decisions,list) or {d.get("featureId") for d in decisions}!=set(expected) or len(decisions)!=len(expected):
        raise ValueError("every mapped contact candidate must be decided exactly once")
    units=correlation_review.get("unitsBottomUp")
    if not isinstance(units,list) or len(units)<2:raise ValueError("correlation requires at least two ordered units")
    unit_ids=[v.get("unitId") for v in units]
    events=[]
    source_events={v["featureId"]:v for v in adjacency["crossings"]}
    for decision in decisions:
        feature_id=decision["featureId"];candidate=expected[feature_id]
        if decision.get("sourcePolygonFeatureIds")!=candidate["sourcePolygonFeatureIds"]:
            raise ValueError("mapped contact source-polygon direction changed")
        action=decision.get("decision")
        if action=="Exclude":
            if not isinstance(decision.get("reason"),str) or not decision["reason"].strip():
                raise ValueError("excluded mapped contact requires a reason")
            continue
        if action!="UseAsSectionContact":raise ValueError("unsupported mapped contact decision")
        index=decision.get("contactIndex");pair=decision.get("modelUnitPair")
        if isinstance(index,bool) or not isinstance(index,int) or not 1<=index<len(unit_ids):
            raise ValueError("mapped contact index must identify an internal contact")
        if not isinstance(pair,list) or len(pair)!=2 or set(pair)!={unit_ids[index-1],unit_ids[index]}:
            raise ValueError("mapped contact model units are not adjacent at contactIndex")
        event=dict(source_events[feature_id]);event["contactIndex"]=index;event["unitPair"]=pair
        event["mappedSourceUnitPair"]=candidate["sourceUnits"]
        event["correlationAuthorization"]="GeologistInterpreted_MappedSurfaceContact"
        events.append(event)
    return {"schemaVersion":"GeographicLineworkIntersections-1.0","events":events,"ambiguities":[],
      "interpretationState":"ReviewedExactMappedSurfaceContacts_NoSubsurfaceContinuation",
      "review":{"reviewer":review["reviewer"],"reviewedAt":review["reviewedAt"],
        "candidateCount":len(expected),"usedCount":len(events),"excludedCount":len(expected)-len(events)}}

def load_and_validate_mapped_contact_review(adjacency_path,correlation_path,review_path):
    adjacency=load_mapped_polygon_adjacency(adjacency_path)
    correlation=json.loads(Path(correlation_path).read_text(encoding="utf-8"))
    review=json.loads(Path(review_path).read_text(encoding="utf-8"))
    return validate_mapped_contact_review(adjacency,correlation,review)
