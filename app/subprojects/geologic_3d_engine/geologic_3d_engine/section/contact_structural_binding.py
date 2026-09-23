"""Bind explicit structural observations to mapped contacts without spatial guessing."""
from __future__ import annotations

import hashlib,json,math
from collections.abc import Mapping,Sequence

from .route_binding import require_matching_route_binding


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()


def propose_contact_structural_bindings(route, intersections:Mapping, template:Mapping,
                                        projected:Mapping, maximum_station_separation_m):
    if isinstance(maximum_station_separation_m,bool) or not isinstance(maximum_station_separation_m,(int,float)) or not math.isfinite(maximum_station_separation_m) or maximum_station_separation_m<0:
        raise ValueError("maximum station separation must be finite and non-negative")
    require_matching_route_binding(route,projected,"structural observation projection")
    if template.get("intersectionEvidenceSha256")!=intersections.get("recordSha256"):
        raise ValueError("orientation template and mapped intersections are not bound")
    observations=projected.get("observations")
    if not isinstance(observations,Sequence):raise ValueError("projected structural observations are required")
    by_event={row.get("eventIndex"):row for row in template.get("hypotheses",[])}
    proposals=[]
    for event_index,event in enumerate(intersections.get("events",[])):
        row=by_event.get(event_index)
        if event.get("kind")!="Contact" or row is None:continue
        candidates=[]
        for observation in observations:
            if observation.get("projectionState")!="Projected":continue
            feature_ids=observation.get("appliesToFeatureIds")
            explicit_feature=isinstance(feature_ids,list) and event.get("featureId") in feature_ids
            explicit_pair=(event.get("unitPair") is not None and observation.get("unitPair")==event.get("unitPair"))
            if not (explicit_feature or explicit_pair):continue
            separation=abs(float(observation["stationM"])-float(event["stationM"]))
            if separation>maximum_station_separation_m:continue
            values=[observation.get(k) for k in ("trueDipDegrees","dipDirectionDegrees",
                "angularUncertaintyDegrees","lateralSupportM")]
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
                continue
            dip,direction,uncertainty,support=map(float,values)
            if not (0<=dip<90 and 0<=direction<360 and 0<=uncertainty and dip+uncertainty<90 and support>0):continue
            candidates.append({"observationId":observation["observationId"],
                "sourceId":observation["sourceId"],"stationSeparationM":separation,
                "bindingBasis":"ExplicitFeatureId" if explicit_feature else "ExplicitUnitPair",
                "trueDipDegrees":dip,"dipDirectionDegrees":direction,
                "angularUncertaintyDegrees":uncertainty,"lateralSupportM":support})
        candidates.sort(key=lambda x:(x["stationSeparationM"],x["observationId"]))
        status="UniqueCandidate" if len(candidates)==1 else ("AmbiguousMultipleCandidates" if candidates else "NoEligibleCandidate")
        proposals.append({"eventIndex":event_index,"hypothesisId":row["hypothesisId"],
            "featureId":event.get("featureId"),"status":status,"candidates":candidates})
    result={"schemaVersion":"ContactStructuralBindingProposals-1.0",
        "intersectionEvidenceSha256":intersections.get("recordSha256"),
        "orientationTemplateSha256":template.get("recordSha256"),
        "structuralProjectionSha256":hashlib.sha256(_canonical(projected)).hexdigest(),
        "maximumStationSeparationM":float(maximum_station_separation_m),"proposals":proposals,
        "uniqueCandidateCount":sum(x["status"]=="UniqueCandidate" for x in proposals),
        "authorizationBoundary":"ExplicitAssociationCandidates_NoAutomaticGeologicalAuthorization"}
    result["recordSha256"]=hashlib.sha256(_canonical(result)).hexdigest();return result


def accept_unique_contact_bindings(template:Mapping, proposals:Mapping, accepted_hypothesis_ids):
    unsigned={k:v for k,v in proposals.items() if k!="recordSha256"}
    if proposals.get("recordSha256")!=hashlib.sha256(_canonical(unsigned)).hexdigest():
        raise ValueError("binding proposal hash mismatch")
    if proposals.get("orientationTemplateSha256")!=template.get("recordSha256"):
        raise ValueError("binding proposal is not bound to this orientation template")
    accepted=set(accepted_hypothesis_ids)
    known={x.get("hypothesisId") for x in proposals.get("proposals",[])}
    if not accepted<=known:raise ValueError("accepted hypothesis ID is unknown")
    result=json.loads(json.dumps(template,ensure_ascii=False))
    rows={row["hypothesisId"]:row for row in result.get("hypotheses",[])}
    for proposal in proposals["proposals"]:
        if proposal["hypothesisId"] not in accepted:continue
        if proposal.get("status")!="UniqueCandidate":raise ValueError("only a unique explicit candidate may be accepted")
        candidate=proposal["candidates"][0];row=rows[proposal["hypothesisId"]]
        row.update({"orientationBasis":"EvidenceCandidate",
            "trueDipDegrees":candidate["trueDipDegrees"],"dipDirectionDegrees":candidate["dipDirectionDegrees"],
            "angularUncertaintyDegrees":candidate["angularUncertaintyDegrees"],
            "lateralSupportM":candidate["lateralSupportM"],"basisSourceIds":[candidate["sourceId"]],
            "interpretationNote":f"Explicitly associated structural observation {candidate['observationId']}; pending independent review",
            "subsurfaceContinuationAuthorized":False})
    result["recordSha256"]=hashlib.sha256(_canonical({k:v for k,v in result.items() if k!="recordSha256"})).hexdigest()
    return result
