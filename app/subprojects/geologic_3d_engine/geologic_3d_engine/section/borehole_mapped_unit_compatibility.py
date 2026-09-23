"""Audit explicit borehole-to-mapped-unit proposals without name-only correlation."""
from __future__ import annotations

import math
from collections.abc import Mapping,Sequence


def _age(record):
    age=record.get("geologicAgeInterval")
    if not isinstance(age,Mapping):return None
    values=[age.get("youngerMa"),age.get("olderMa")]
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):return None
    younger,older=map(float,values)
    if younger<0 or older<younger:return None
    authority=age.get("timeScaleAuthority");version=age.get("timeScaleVersion")
    if not all(isinstance(x,str) and x.strip() for x in (authority,version)):return None
    return younger,older,authority,version


def _term(record):
    required=("sourceLabel","normalizedLabel","normalizationAuthority","vocabularyVersion","termStatus")
    if not all(isinstance(record.get(k),str) and record[k].strip() for k in required):return None
    return tuple(record[k] for k in required)


def audit_borehole_mapped_unit_compatibility(borehole_role, borehole_units, mapped_units,
                                             proposed_pairs):
    if borehole_role not in {"GeometryConstraint","RegionalContextOnly","OutOfScope"}:
        raise ValueError("borehole route role is invalid")
    if not all(isinstance(x,Sequence) and not isinstance(x,(str,bytes)) for x in (borehole_units,mapped_units,proposed_pairs)):
        raise ValueError("unit and proposal collections are required")
    holes={x.get("unitId"):x for x in borehole_units if isinstance(x,Mapping)}
    maps={x.get("unitId"):x for x in mapped_units if isinstance(x,Mapping)}
    if None in holes or len(holes)!=len(borehole_units) or None in maps or len(maps)!=len(mapped_units):
        raise ValueError("unit IDs must be present and unique")
    rows=[];seen=set()
    for pair in proposed_pairs:
        if not isinstance(pair,Mapping) or set(pair)!={"boreholeUnitId","mappedUnitId"}:
            raise ValueError("each proposal must contain exactly two unit IDs")
        key=(pair["boreholeUnitId"],pair["mappedUnitId"])
        if key in seen or key[0] not in holes or key[1] not in maps:raise ValueError("proposal is duplicate or references an unknown unit")
        seen.add(key);hole,mapped=holes[key[0]],maps[key[1]];reasons=[]
        if borehole_role!="GeometryConstraint":reasons.append("BoreholeNotAuthorizedAsGeometryConstraint")
        ht,mt=_term(hole),_term(mapped)
        if ht is None or mt is None:reasons.append("IncompleteTerminologyProvenance")
        elif ht[1]!=mt[1]:reasons.append("NormalizedTermMismatch")
        elif ht[2:4]!=mt[2:4]:reasons.append("VocabularyIdentityMismatch")
        if hole.get("evidenceStatus") not in {"Observed","Literature","IndependentlyVerified"} or mapped.get("evidenceStatus") not in {"Observed","Literature","IndependentlyVerified"}:
            reasons.append("EvidenceStatusInsufficient")
        ha,ma=_age(hole),_age(mapped)
        if ha is None or ma is None:reasons.append("GeologicAgeMissingOrInvalid")
        elif ha[2:]!=ma[2:]:reasons.append("TimeScaleIdentityMismatch")
        elif max(ha[0],ma[0])>min(ha[1],ma[1]):reasons.append("GeologicAgeIntervalsDisjoint")
        for side in ("eventBoundaryAbove","eventBoundaryBelow"):
            a,b=hole.get(side),mapped.get(side)
            if a is not None and b is not None and a!=b:reasons.append(f"{side}Conflict")
        rows.append({**pair,"status":"CompatibleCandidate" if not reasons else "Rejected",
            "reasons":reasons,"geometryAuthorizationGranted":False})
    return {"schemaVersion":"BoreholeMappedUnitCompatibilityAudit-1.0",
        "proposalCount":len(rows),"compatibleCandidateCount":sum(x["status"]=="CompatibleCandidate" for x in rows),
        "results":rows,"realRegionAuthorized":False,
        "authorizationBoundary":"CompatibilityScreenOnly_ExplicitCorrelationReviewStillRequired"}
