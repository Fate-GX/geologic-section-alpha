"""Validate mapped polygon identities sampled on both sides of a crossing."""
import hashlib,json
from pathlib import Path

def load_mapped_polygon_adjacency(path):
    payload=json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schemaVersion")!="GsjRouteCrossingSideClassification-1.0":
        raise ValueError("unsupported mapped polygon adjacency schema")
    claimed=payload.get("recordSha256")
    unsigned={key:value for key,value in payload.items() if key!="recordSha256"}
    actual=hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()
    if claimed!=actual:raise ValueError("mapped polygon adjacency hash mismatch")
    rows=payload.get("crossings")
    if not isinstance(rows,list) or payload.get("crossingCount")!=len(rows):
        raise ValueError("mapped polygon adjacency crossing count mismatch")
    if payload.get("authorizationBoundary")!="MappedSurfaceAdjacencyOnly_NoSubsurfaceContinuation":
        raise ValueError("mapped polygon adjacency overstates authorization")
    for row in rows:
        status=row.get("sideClassificationStatus")
        pair=row.get("unitPair")
        if status=="MappedUnitTransition":
            if not isinstance(pair,list) or len(pair)!=2:raise ValueError("mapped transition lacks two units")
            ids=[item.get("sourcePolygonFeatureId") for item in pair]
            if None in ids or ids[0]==ids[1]:raise ValueError("mapped transition unit identities are invalid")
        elif pair is not None:raise ValueError("unresolved crossing cannot carry a unit pair")
    return payload


def select_geologic_contact_intersections(intersections, adjacency, station_tolerance_m=.05):
    """Retain only contact events proven to separate two mapped geologic units."""
    if not isinstance(station_tolerance_m,(int,float)) or isinstance(station_tolerance_m,bool) or station_tolerance_m<=0:
        raise ValueError("positive station tolerance is required")
    selected=[]
    rows=adjacency.get("crossings",[]) if isinstance(adjacency,dict) else []
    for event in intersections.get("events",[]):
        if event.get("kind")!="Contact":continue
        matches=[row for row in rows if row.get("featureId")==event.get("featureId") and
                 isinstance(row.get("stationM"),(int,float)) and
                 abs(float(row["stationM"])-float(event.get("stationM",float("inf"))))<=station_tolerance_m]
        if len(matches)!=1:raise ValueError("contact intersection requires one polygon-side classification")
        if matches[0].get("sideClassificationStatus")=="MappedUnitTransition":
            selected.append({**event,"mappedUnitPair":matches[0]["unitPair"],
                             "surfaceClassification":"MappedUnitTransition"})
    return selected
