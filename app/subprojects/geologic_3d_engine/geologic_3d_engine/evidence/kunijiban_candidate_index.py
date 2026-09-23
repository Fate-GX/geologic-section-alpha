"""Index KuniJiban map markers as unverified borehole candidates."""
from __future__ import annotations

import hashlib
import json
import math

from ..section.map_template import MeasuredRoute2D

MARKER_URL = "https://www.kunijiban.pwri.go.jp/viewer/server/markers.php?x={x}&y={y}&z={z}"


def route_marker_tiles(route, zoom=13):
    if zoom != 13:
        raise ValueError("the official viewer marker layer is declared at zoom 13")
    values=[];n=2**zoom
    for lon,lat in route:
        if not -180<=lon<=180 or not -85.05112878<=lat<=85.05112878:
            raise ValueError("route vertex is outside Web Mercator")
        x=int((lon+180)/360*n)
        y=int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)
        values.append((x,y))
    return [(x,y,zoom) for x in range(min(v[0] for v in values),max(v[0] for v in values)+1)
            for y in range(min(v[1] for v in values),max(v[1] for v in values)+1)]


def build_candidate_index(route, responses):
    lat0=sum(float(p[1]) for p in route)/len(route)
    sx=6378137*math.cos(math.radians(lat0))*math.pi/180;sy=6378137*math.pi/180
    measured=MeasuredRoute2D([[float(p[0])*sx,float(p[1])*sy] for p in route])
    rows=[];tile_hashes={}
    for response in responses:
        if len(response) not in {2,3}:
            raise ValueError("each marker response requires tile, document and optional raw SHA-256")
        tile,data=response[:2]
        raw=json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
        digest=(response[2] if len(response)==3 else hashlib.sha256(raw).hexdigest())
        if (not isinstance(digest,str) or len(digest)!=64 or
                any(character not in "0123456789abcdef" for character in digest)):
            raise ValueError("marker response SHA-256 is invalid")
        tile_hashes[f"{tile[0]}/{tile[1]}/{tile[2]}"]=digest
        if data.get("header",{}).get("success") is not True:
            raise ValueError("KuniJiban marker response was unsuccessful")
        for item in data.get("data",{}).get("values",[]):
            point=[[float(item["longitude"])*sx,float(item["latitude"])*sy]]
            projected=measured.project(point)
            rows.append({"providerRecordId":int(item["id"]),
              "longitude":float(item["longitude"]),"latitude":float(item["latitude"]),
              "stationM":float(projected["station"][0]),
              "projectionDistanceM":float(projected["projectionDistance"][0]),
              "providerApprovalLabel":item.get("approval"),
              "evidenceStatus":"UnverifiedProviderCandidate",
              "authorizationBoundary":"IndexMarkerOnly_NoElevationOrLithologyAuthorization"})
    rows.sort(key=lambda row:(row["projectionDistanceM"],row["providerRecordId"]))
    payload={"schemaVersion":"KuniJibanRouteCandidateIndex-1.0",
      "sourceId":"KUNIJIBAN-OFFICIAL-VIEWER","markerZoom":13,
      "markerEndpoint":MARKER_URL,"tileResponseSha256":tile_hashes,
      "candidateCount":len(rows),"candidates":rows,
      "providerDataStatus":"OfficialSiteStatesCurrentlyPublishedDataAreUninspected",
      "providerApprovalInterpretation":"PreservedLabel_NotIndependentEvidenceVerification",
      "realSubsurfaceGeometryAuthorized":False}
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    payload["recordSha256"]=hashlib.sha256(canonical).hexdigest()
    return payload
