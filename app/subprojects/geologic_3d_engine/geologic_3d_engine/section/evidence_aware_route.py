"""Propose, but never silently apply, routes through point evidence."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence


def _distance_m(a, b):
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    value = (math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*
             math.sin((lon2-lon1)/2)**2)
    return 6378137.0*2*math.asin(min(1.0, math.sqrt(value)))


def _checked_point(point, name):
    if (not isinstance(point, Sequence) or isinstance(point, (str, bytes)) or len(point) != 2 or
            any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                not math.isfinite(v) for v in point)):
        raise ValueError(f"{name} must be a finite longitude/latitude pair")
    lon, lat = map(float, point)
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError(f"{name} longitude/latitude are invalid")
    return [lon, lat]


def _proper_route_intersections(route):
    lat0=math.radians(sum(point[1] for point in route)/len(route))
    xy=[(math.radians(point[0])*math.cos(lat0),math.radians(point[1])) for point in route]
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    found=[]
    for i,(a,b) in enumerate(zip(xy,xy[1:])):
        for j,(c,d) in enumerate(zip(xy,xy[1:])):
            if j<=i+1:continue
            values=(cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b))
            if values[0]*values[1]<0 and values[2]*values[3]<0:
                found.append([i,j])
    return found


def propose_minimum_detour_route(route_lonlat, evidence_point_lonlat):
    """Insert a point into the segment with minimum added great-circle length."""
    if (not isinstance(route_lonlat, Sequence) or isinstance(route_lonlat, (str, bytes)) or
            len(route_lonlat) < 2):
        raise ValueError("route requires at least two vertices")
    route = [_checked_point(point, "route vertex") for point in route_lonlat]
    if any(_distance_m(a, b) == 0 for a, b in zip(route, route[1:])):
        raise ValueError("route contains a zero-length segment")
    point = _checked_point(evidence_point_lonlat, "evidence point")
    original = sum(_distance_m(a, b) for a, b in zip(route, route[1:]))
    additions = [_distance_m(a, point)+_distance_m(point, b)-_distance_m(a, b)
                 for a, b in zip(route, route[1:])]
    segment = min(range(len(additions)), key=lambda i: (additions[i], i))
    candidate = route[:segment+1]+[point]+route[segment+1:]
    candidate_length = original+additions[segment]
    station = sum(_distance_m(a, b) for a, b in zip(candidate[:segment+1],
                                                     candidate[1:segment+2]))
    intersections=_proper_route_intersections(candidate)
    return {"originalRouteLonLat": route, "candidateRouteLonLat": candidate,
            "insertedAfterSegmentIndex": segment, "evidenceStationM": station,
            "originalLengthM": original, "candidateLengthM": candidate_length,
            "additionalLengthM": additions[segment],
            "properSelfIntersectionSegmentPairs":intersections,
            "routeTopologyStatus":"Simple" if not intersections else "SelfIntersecting",
            "selectionMethod":"MinimumAddedGreatCirclePolylineLength",
            "applicationState":"ProposalOnly_UserMustExplicitlySelect"}


def build_evidence_aware_route_candidate(route_lonlat, borehole):
    if not isinstance(borehole, Mapping):
        raise ValueError("borehole must be an object")
    required = ("boreholeId", "longitude", "latitude", "horizontalCrsStatus",
                "verticalDatumStatus", "sourceId", "intervals")
    if any(key not in borehole for key in required):
        raise ValueError("borehole is incomplete")
    proposal = propose_minimum_detour_route(route_lonlat,
                                            [borehole["longitude"], borehole["latitude"]])
    blockers = []
    if borehole["horizontalCrsStatus"] != "Verified":
        blockers.append("HorizontalCrsNotVerified")
    if borehole["verticalDatumStatus"] != "Verified":
        blockers.append("VerticalDatumNotVerified")
    if borehole.get("collarElevationAccuracyStatus") not in {"Declared","Verified"}:
        blockers.append("CollarElevationAccuracyNotVerified")
    if not borehole["intervals"] or any(row.get("evidenceStatus") != "Observed"
                                        for row in borehole["intervals"]):
        blockers.append("IntervalsNotObserved")
    proposal.update({"boreholeId": borehole["boreholeId"], "sourceId": borehole["sourceId"],
        "horizontalCollocationIfSelected": True,
        "sectionConstraintEligibleIfSelected": not blockers,
        "eligibilityBlockers": blockers,
        "boundary":"RouteGeometryProposal_NotAutomaticEvidenceAcceptance"})
    canonical=json.dumps(proposal,sort_keys=True,separators=(",",":"),
                         ensure_ascii=False).encode("utf-8")
    proposal["recordSha256"]=hashlib.sha256(canonical).hexdigest()
    return proposal
