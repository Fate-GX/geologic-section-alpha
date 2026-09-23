"""Apply reviewed, version-bound named-age crosswalks without silent equivalence."""
from __future__ import annotations

import hashlib,json,math
from collections.abc import Mapping


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()


def apply_named_age_crosswalk(unit_catalog:Mapping,crosswalk:Mapping):
    for document,name,schema in ((unit_catalog,"unit catalog","MappedGeologicUnitCatalog-1.0"),
                                 (crosswalk,"crosswalk","ChronostratigraphicNamedAgeCrosswalk-1.0")):
        unsigned={k:v for k,v in document.items() if k!="recordSha256"}
        if document.get("schemaVersion")!=schema or document.get("recordSha256")!=hashlib.sha256(_canonical(unsigned)).hexdigest():
            raise ValueError(f"{name} is invalid or hash-mismatched")
    authority=crosswalk.get("targetTimeScaleAuthority");version=crosswalk.get("targetTimeScaleVersion")
    if not all(isinstance(x,str) and x.strip() for x in (authority,version)):raise ValueError("target time-scale identity is required")
    rows=crosswalk.get("mappings")
    if not isinstance(rows,list) or not rows:raise ValueError("at least one named-age mapping is required")
    mapping={}
    for row in rows:
        required={"sourceLabel","sourceLabelEnglish","youngerMa","olderMa","mappingStatus","targetUnits","sourceIds"}
        if not isinstance(row,Mapping) or not required.issubset(row):raise ValueError("named-age mapping is incomplete")
        key=(row["sourceLabel"],row["sourceLabelEnglish"])
        if key in mapping:raise ValueError("named-age mapping keys must be unique")
        younger,older=row["youngerMa"],row["olderMa"]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (younger,older)) or younger<0 or older<younger:
            raise ValueError("named-age numerical interval is invalid")
        if row["mappingStatus"] not in {"ExactFormalUnit","ConservativeEnvelope_NotExactUnitEquivalence"}:
            raise ValueError("named-age mapping status is unsupported")
        if not isinstance(row["targetUnits"],list) or not row["targetUnits"] or not isinstance(row["sourceIds"],list) or not row["sourceIds"]:
            raise ValueError("target units and sources are required")
        mapping[key]=row
    result=json.loads(json.dumps(unit_catalog,ensure_ascii=False));matched=0
    for unit in result["units"]:
        row=mapping.get((unit.get("sourceAgeLabel"),unit.get("sourceAgeLabelEnglish")))
        if row is None:continue
        unit["geologicAgeInterval"]={"youngerMa":float(row["youngerMa"]),"olderMa":float(row["olderMa"]),
            "timeScaleAuthority":authority,"timeScaleVersion":version,"targetUnits":row["targetUnits"],
            "mappingStatus":row["mappingStatus"],"basisSourceIds":row["sourceIds"],
            "intervalConvention":"ClosedConservativeEnvelope_MaBeforePresent"}
        unit["numericAgeStatus"]="VersionBoundCrosswalkApplied";matched+=1
    result["schemaVersion"]="MappedGeologicUnitCatalogWithAgeCrosswalk-1.0"
    result["sourceUnitCatalogSha256"]=unit_catalog["recordSha256"]
    result["ageCrosswalkSha256"]=crosswalk["recordSha256"]
    result["ageMappedUnitCount"]=matched;result["realRegionSubsurfaceAuthorized"]=False
    result["authorizationBoundary"]="NamedAgeNormalizationOnly_NoDepositionalAgePrecisionOrSubsurfaceAuthorization"
    result.pop("recordSha256",None);result["recordSha256"]=hashlib.sha256(_canonical(result)).hexdigest();return result
