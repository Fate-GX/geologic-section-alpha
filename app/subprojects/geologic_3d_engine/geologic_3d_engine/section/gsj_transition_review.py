"""Review interval-censored GSJ point-query transitions as map-contact events."""
import hashlib,json,math
from typing import Mapping
import numpy as np

def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def build_transition_review_template(plan):
    geology=plan.get("surfaceGeology",{});candidates=[]
    for index,item in enumerate(geology.get("transitions",[])):
        candidates.append({"transitionId":f"GSJ-TRANSITION-{index}","leftSymbol":item.get("leftSymbol"),
          "rightSymbol":item.get("rightSymbol"),"lowerStationM":item.get("lowerStationM"),
          "upperStationM":item.get("upperStationM"),"estimatedStationM":item.get("estimatedStationM"),
          "uncertaintyM":item.get("uncertaintyM"),"locatorStatus":item.get("locatorStatus"),
          "reviewEligibility":"Eligible" if item.get("leftSymbol") and item.get("rightSymbol") else "Ineligible_NoMappedUnit"})
    return {"schemaVersion":"GsjSurfaceTransitionReview-1.0","planSha256":canonical_sha256(plan),
      "reviewer":"","reviewedAt":"","reviewStatus":"Draft_NotReviewed","candidates":candidates,"assignments":[],
      "instructions":"Assign only Eligible transitions to a contactIndex and select a station within the retained bracket."}

def validate_transition_review(plan,review):
    required={"schemaVersion","planSha256","reviewer","reviewedAt","reviewStatus","candidates","assignments"}
    if not isinstance(review,Mapping) or not required.issubset(review):raise ValueError("GSJ transition review is incomplete")
    if review["schemaVersion"]!="GsjSurfaceTransitionReview-1.0" or review["reviewStatus"]!="GeologistInterpreted":raise ValueError("review must be explicitly GeologistInterpreted")
    if review["planSha256"]!=canonical_sha256(plan):raise ValueError("transition review is not bound to this plan evidence")
    if not review["reviewer"] or not review["reviewedAt"]:raise ValueError("reviewer and review time are required")
    expected={v["transitionId"]:v for v in build_transition_review_template(plan)["candidates"]}
    events=[];seen=set();profile=plan["terrainProfile"];stations=np.asarray([v["stationM"] for v in profile]);terrain=np.asarray([v["elevationM"] for v in profile])
    for item in review["assignments"]:
        if not isinstance(item,Mapping) or set(item)!={"transitionId","contactIndex","selectedStationM","unitPair"}:raise ValueError("invalid transition assignment")
        candidate=expected.get(item["transitionId"])
        if candidate is None or item["transitionId"] in seen:raise ValueError("unknown or duplicate transition assignment")
        seen.add(item["transitionId"])
        if candidate["reviewEligibility"]!="Eligible":raise ValueError("NoMappedUnit transition cannot become a contact")
        selected=item["selectedStationM"];index=item["contactIndex"]
        if isinstance(selected,bool) or not isinstance(selected,(int,float)) or not math.isfinite(selected) or not candidate["lowerStationM"]<=selected<=candidate["upperStationM"]:raise ValueError("selected station must lie inside transition bracket")
        if isinstance(index,bool) or not isinstance(index,int) or index<0:raise ValueError("contactIndex must be a non-negative integer")
        if item["unitPair"]!=[candidate["leftSymbol"],candidate["rightSymbol"]]:raise ValueError("assigned unit pair must preserve mapped symbols and direction")
        events.append({"featureId":item["transitionId"],"kind":"Contact","stationM":float(selected),"contactIndex":index,
          "unitPair":item["unitPair"],"terrainElevationM":float(np.interp(selected,stations,terrain)),
          "lowerStationM":candidate["lowerStationM"],"upperStationM":candidate["upperStationM"],
          "horizontalUncertaintyM":max(selected-candidate["lowerStationM"],candidate["upperStationM"]-selected),
          "sourceId":"GSJ-SEAMLESS-V2-API","sourceUrl":"https://gbank.gsj.jp/seamless/v2/api/1.3.1/",
          "locationMethod":"IntervalCensoredBetweenPointQueries","locationalConfidence":"SamplingIntervalLimited"})
    return {"schemaVersion":"GeographicLineworkIntersections-1.0","events":events,"ambiguities":[],
      "interpretationState":"ReviewedIntervalCensoredSurfaceTransitions_NotExactMapLines"}
