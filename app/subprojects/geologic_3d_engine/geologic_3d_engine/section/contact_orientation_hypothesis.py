"""Explicit, non-authorizing orientation hypotheses for mapped contacts."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping

from .map_template import apparent_dip_degrees


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _verify_intersections(document):
    if (not isinstance(document, Mapping) or document.get("schemaVersion") !=
            "GeographicLineworkIntersections-1.0"):
        raise ValueError("geographic linework intersections are required")
    unsigned = {k:v for k,v in document.items() if k != "recordSha256"}
    if document.get("recordSha256") != hashlib.sha256(_canonical(unsigned)).hexdigest():
        raise ValueError("intersection evidence hash mismatch")
    events = document.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("at least one mapped intersection is required")
    return events


def _slope_bounds(dip, direction, angular_uncertainty, section_azimuth):
    """Exact extrema of dz/ds=-tan(dip)*cos(direction-section azimuth).

    The single declared angular uncertainty is conservatively applied to both
    true dip and dip direction. Extrema occur at dip interval endpoints and at
    direction endpoints or cosine extrema inside the unwrapped interval.
    """
    dip_lo=max(0.0,dip-angular_uncertainty)
    dip_hi=dip+angular_uncertainty
    if dip_hi>=90.0:
        raise ValueError("dip uncertainty reaches a vertical/non-single-valued plane")
    dir_lo=direction-angular_uncertainty;dir_hi=direction+angular_uncertainty
    directions=[dir_lo,dir_hi]
    for base in (section_azimuth,section_azimuth+180.0):
        for turns in range(-2,3):
            candidate=base+360.0*turns
            if dir_lo<=candidate<=dir_hi:directions.append(candidate)
    values=[-math.tan(math.radians(d))*math.cos(math.radians(a-section_azimuth))
            for d in (dip_lo,dip_hi) for a in directions]
    return min(values),max(values)


def build_contact_orientation_hypothesis_template(intersections: Mapping):
    events = _verify_intersections(intersections)
    rows=[]
    for index,event in enumerate(events):
        if event.get("kind") != "Contact":
            continue
        station,elevation=event.get("stationM"),event.get("terrainElevationM")
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)
               for v in (station,elevation)):
            raise ValueError("contact anchor station/elevation is invalid")
        rows.append({"hypothesisId":f"CONTACT-ORIENTATION-{index:04d}",
            "eventIndex":index,"featureId":event.get("featureId"),
            "routeSegmentIndex":event.get("routeSegmentIndex"),
            "sourceId":event.get("sourceId"),"anchorStationM":float(station),
            "anchorElevationM":float(elevation),
            "orientationBasis":"NeedsInput",
            "trueDipDegrees":None,"dipDirectionDegrees":None,
            "angularUncertaintyDegrees":None,"lateralSupportM":None,
            "basisSourceIds":[],"interpretationNote":"",
            "subsurfaceContinuationAuthorized":False})
    result={"schemaVersion":"ContactOrientationHypothesisTemplate-1.0",
        "intersectionEvidenceSha256":intersections["recordSha256"],"hypotheses":rows,
        "equation":"alpha=atan(tan(delta)*cos(theta_dip-theta_section)); dz/ds=-tan(alpha)",
        "coordinateConvention":"station increases along route; elevation positive upward; dip direction is clockwise from north",
        "authorizationBoundary":"InputTemplate_NoSubsurfaceContinuation"}
    result["recordSha256"]=hashlib.sha256(_canonical(result)).hexdigest()
    return result


def evaluate_contact_orientation_hypotheses(template: Mapping,
                                            section_azimuths_by_event: Mapping):
    if template.get("schemaVersion") != "ContactOrientationHypothesisTemplate-1.0":
        raise ValueError("unsupported contact-orientation template")
    claimed=template.get("recordSha256")
    unsigned={k:v for k,v in template.items() if k!="recordSha256"}
    if claimed!=hashlib.sha256(_canonical(unsigned)).hexdigest():
        raise ValueError("contact-orientation template hash mismatch")
    output=[]
    for row in template.get("hypotheses",[]):
        basis=row.get("orientationBasis")
        if basis=="NeedsInput":
            continue
        if basis not in {"SyntheticAssumption","EvidenceCandidate"}:
            raise ValueError("orientation basis is unsupported or prematurely authorized")
        values=[row.get(k) for k in ("trueDipDegrees","dipDirectionDegrees",
                                      "angularUncertaintyDegrees","lateralSupportM")]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)
               for v in values):
            raise ValueError("orientation values and uncertainty/support must be finite")
        dip,direction,uncertainty,support=map(float,values)
        if not 0<=dip<90 or not 0<=direction<360 or not 0<=uncertainty<=90 or support<=0:
            raise ValueError("orientation values lie outside the declared domain")
        event_index=row.get("eventIndex")
        azimuth=section_azimuths_by_event.get(event_index)
        if isinstance(azimuth,bool) or not isinstance(azimuth,(int,float)) or not math.isfinite(azimuth):
            raise ValueError("section azimuth is missing for a contact event")
        alpha=apparent_dip_degrees(dip,direction,float(azimuth))
        if abs(alpha)>=89.999999:
            raise ValueError("near-vertical apparent dip cannot be represented as elevation by station")
        slope=-math.tan(math.radians(alpha))
        slope_lo,slope_hi=_slope_bounds(dip,direction,uncertainty,float(azimuth))
        station=float(row["anchorStationM"]);z=float(row["anchorElevationM"])
        endpoints=[[station-support,z-slope*support],
                   [station+support,z+slope*support]]
        envelope=[]
        for sample_station in (station-support,station,station+support):
            dz=sample_station-station
            candidates=(z+slope_lo*dz,z+slope_hi*dz)
            envelope.append({"stationM":sample_station,
                             "minimumElevationM":min(candidates),
                             "maximumElevationM":max(candidates)})
        output.append({"hypothesisId":row["hypothesisId"],"eventIndex":event_index,
            "featureId":row.get("featureId"),"sourceId":row.get("sourceId"),
            "orientationBasis":basis,"sectionAzimuthDegrees":float(azimuth),
            "trueDipDegrees":dip,"dipDirectionDegrees":direction,
            "apparentDipDegrees":alpha,"elevationSlopePerStation":slope,
            "elevationSlopeRangePerStation":[slope_lo,slope_hi],
            "supportIntervalM":[station-support,station+support],
            "candidateEndpointsStationElevation":endpoints,
            "uncertaintyEnvelope":envelope,
            "uncertaintyConvention":"SameSymmetricAngularBoundAppliedToTrueDipAndDipDirection",
            "subsurfaceContinuationAuthorized":False})
    return {"schemaVersion":"ContactOrientationHypothesisEvaluation-1.0",
        "evaluatedCount":len(output),"hypotheses":output,
        "realRegionAuthorized":False,
        "authorizationBoundary":"DiagnosticCandidateGeometry_NoSectionGeneration"}


def audit_contact_hypothesis_topology(evaluation: Mapping, order_relations):
    """Prove or reject declared above/below relations over shared support."""
    if evaluation.get("schemaVersion")!="ContactOrientationHypothesisEvaluation-1.0":
        raise ValueError("contact-orientation evaluation is required")
    hypotheses=evaluation.get("hypotheses")
    if not isinstance(hypotheses,list):raise ValueError("hypothesis array is required")
    by_id={row.get("hypothesisId"):row for row in hypotheses}
    if len(by_id)!=len(hypotheses):raise ValueError("hypothesis IDs must be unique")
    results=[]
    for relation in order_relations:
        if not isinstance(relation,Mapping):raise ValueError("order relation must be an object")
        above=by_id.get(relation.get("aboveHypothesisId"));below=by_id.get(relation.get("belowHypothesisId"))
        gap=relation.get("minimumSeparationM",0.0)
        if above is None or below is None or above is below:
            raise ValueError("order relation references invalid hypotheses")
        if isinstance(gap,bool) or not isinstance(gap,(int,float)) or not math.isfinite(gap) or gap<0:
            raise ValueError("minimum separation must be finite and non-negative")
        lo=max(above["supportIntervalM"][0],below["supportIntervalM"][0])
        hi=min(above["supportIntervalM"][1],below["supportIntervalM"][1])
        if lo>=hi:
            results.append({**dict(relation),"sharedSupportIntervalM":None,
                            "status":"NoSharedSupport_NotTestable"})
            continue
        def range_at(row,s):
            anchor_station=row["candidateEndpointsStationElevation"][0][0]
            # The nominal endpoints are support bounds, so recover the anchor at
            # their midpoint; its elevation follows the nominal line.
            support=row["supportIntervalM"]
            anchor=(support[0]+support[1])/2
            nominal=row["candidateEndpointsStationElevation"][0][1]+row["elevationSlopePerStation"]*(anchor-anchor_station)
            slopes=row["elevationSlopeRangePerStation"]
            values=[nominal+m*(s-anchor) for m in slopes]
            return min(values),max(values)
        margins=[];nominal_margins=[]
        for s in (lo,hi):
            ar=range_at(above,s);br=range_at(below,s)
            margins.append(ar[0]-br[1]-float(gap))
            def nominal(row):
                left=row["candidateEndpointsStationElevation"][0]
                return left[1]+row["elevationSlopePerStation"]*(s-left[0])
            nominal_margins.append(nominal(above)-nominal(below)-float(gap))
        if min(nominal_margins)<0:status="NominalOrderViolation"
        elif min(margins)<0:status="UncertaintyEnvelopeOverlap"
        else:status="OrderProvenWithinDeclaredEnvelope"
        results.append({**dict(relation),"sharedSupportIntervalM":[lo,hi],
            "endpointWorstCaseMarginsM":margins,"endpointNominalMarginsM":nominal_margins,
            "minimumWorstCaseMarginM":min(margins),"status":status})
    passed=bool(results) and all(r["status"]=="OrderProvenWithinDeclaredEnvelope" for r in results)
    return {"schemaVersion":"ContactHypothesisTopologyAudit-1.0",
            "relationCount":len(results),"passed":passed,"relations":results,
            "authorizationBoundary":"TopologyCompatibilityOnly_NotGeologicalAuthorization"}
