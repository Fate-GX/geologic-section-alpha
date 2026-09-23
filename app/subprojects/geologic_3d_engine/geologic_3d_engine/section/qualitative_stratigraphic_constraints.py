"""Validate source-bound qualitative stratigraphic relations.

This layer preserves order/topology evidence from sketches or explanatory
figures without converting unscaled artwork into elevations, thicknesses or
dips.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


FORBIDDEN_NUMERIC_GEOMETRY_KEYS = {
    "elevationM", "thicknessM", "dipDegrees", "strikeDegrees",
    "contactCoordinates", "controlPoints", "scaleMPerPixel",
}
ALLOWED_RELATIONS = {"Overlies", "UnconformableAbove", "CoversOlderSurface"}


def _walk_forbidden(value):
    if isinstance(value, dict):
        if FORBIDDEN_NUMERIC_GEOMETRY_KEYS & set(value):
            raise ValueError("qualitative evidence cannot carry numeric geometry")
        for child in value.values():
            _walk_forbidden(child)
    elif isinstance(value, list):
        for child in value:
            _walk_forbidden(child)


def validate_qualitative_stratigraphic_constraints(payload):
    if not isinstance(payload, dict) or payload.get("schemaVersion") != "QualitativeStratigraphicConstraints-1.0":
        raise ValueError("unsupported qualitative stratigraphic schema")
    claimed=payload.get("recordSha256")
    unsigned={k:v for k,v in payload.items() if k!="recordSha256"}
    actual=hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),
        ensure_ascii=False).encode()).hexdigest()
    if claimed!=actual:
        raise ValueError("qualitative stratigraphic evidence hash mismatch")
    _walk_forbidden(unsigned)
    if payload.get("geometryAuthorization") != "TopologyAndRelativeOrderOnly_NoNumericGeometry":
        raise ValueError("qualitative evidence cannot authorize numeric geometry")
    units=payload.get("units")
    relations=payload.get("relations")
    if not isinstance(units,list) or not units or not isinstance(relations,list) or not relations:
        raise ValueError("units and relations are required")
    ids=[]
    for unit in units:
        if (not isinstance(unit,dict) or set(unit)!={"unitId","sourceLabel","termStatus"} or
                not all(isinstance(unit[k],str) and unit[k].strip() for k in unit) or
                unit["termStatus"] not in {"Current","Legacy","LocalRelativeUnit","Unverified"}):
            raise ValueError("invalid qualitative unit declaration")
        ids.append(unit["unitId"])
    if len(ids)!=len(set(ids)):
        raise ValueError("qualitative unit IDs must be unique")
    edges={unit_id:set() for unit_id in ids}
    indegree={unit_id:0 for unit_id in ids}
    for relation in relations:
        required={"olderUnitId","youngerUnitId","relationKind","sourceId","locator","evidenceStatus"}
        if not isinstance(relation,dict) or set(relation)!=required or not required.issubset(relation):
            raise ValueError("invalid qualitative relation declaration")
        older,younger=relation["olderUnitId"],relation["youngerUnitId"]
        if older not in edges or younger not in edges or older==younger:
            raise ValueError("qualitative relation references invalid units")
        if relation["relationKind"] not in ALLOWED_RELATIONS:
            raise ValueError("unsupported qualitative relation kind")
        if relation["evidenceStatus"] not in {"Observed","Literature","InterpretedFromSourceFigure"}:
            raise ValueError("invalid qualitative evidence status")
        if not all(isinstance(relation[k],str) and relation[k].strip()
                   for k in ("sourceId","locator")):
            raise ValueError("relation source and locator are required")
        if younger not in edges[older]:
            edges[older].add(younger); indegree[younger]+=1
    queue=sorted(k for k,v in indegree.items() if v==0)
    order=[]
    while queue:
        node=queue.pop(0); order.append(node)
        for child in sorted(edges[node]):
            indegree[child]-=1
            if indegree[child]==0:
                queue.append(child); queue.sort()
    if len(order)!=len(ids):
        raise ValueError("qualitative stratigraphic relations contain a cycle")
    return {"passed":True,"topologicalOrderOldestToYoungest":order,
            "orderedPairs":[[row["olderUnitId"],row["youngerUnitId"]]
                            for row in relations],
            "relationCount":len(relations),"numericGeometryAuthorized":False,
            "sourceIds":sorted({row["sourceId"] for row in relations})}


def load_qualitative_stratigraphic_constraints(path):
    return validate_qualitative_stratigraphic_constraints(
        json.loads(Path(path).read_text(encoding="utf-8")))
