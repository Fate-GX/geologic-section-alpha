"""Create stable source-unit identities from mapped polygon-side evidence."""
from __future__ import annotations

import hashlib,json
from collections.abc import Mapping


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()


def build_mapped_unit_catalog(side_classification:Mapping, *, source_year,
                              source_authority, vocabulary_version):
    unsigned={k:v for k,v in side_classification.items() if k!="recordSha256"}
    if side_classification.get("recordSha256")!=hashlib.sha256(_canonical(unsigned)).hexdigest():
        raise ValueError("mapped crossing-side evidence hash mismatch")
    if side_classification.get("schemaVersion")!="GsjRouteCrossingSideClassification-1.0":
        raise ValueError("mapped crossing-side evidence is required")
    if not all(isinstance(x,str) and x.strip() for x in (source_year,source_authority,vocabulary_version)):
        raise ValueError("source and vocabulary identity are required")
    source_id=side_classification.get("sourceId");units={};pairs=[]
    for crossing in side_classification.get("crossings",[]):
        if crossing.get("sideClassificationStatus")!="MappedUnitTransition":
            continue
        ids=[]
        for raw in crossing.get("unitPair",[]):
            feature_id=raw.get("sourcePolygonFeatureId")
            if isinstance(feature_id,bool) or not isinstance(feature_id,int):
                raise ValueError("mapped polygon feature ID must be an integer")
            hierarchy=[]
            for legend in raw.get("legends",[]):
                if not isinstance(legend,Mapping) or not isinstance(legend.get("level"),int):
                    raise ValueError("mapped unit legend is invalid")
                hierarchy.append({"level":legend["level"],"sourceLabel":legend.get("sourceLabel"),
                    "sourceLabelEnglish":legend.get("sourceLabelEnglish")})
            hierarchy.sort(key=lambda x:x["level"])
            labels=[x for x in hierarchy if isinstance(x.get("sourceLabel"),str) and x["sourceLabel"].strip()]
            english=[x for x in hierarchy if isinstance(x.get("sourceLabelEnglish"),str) and x["sourceLabelEnglish"].strip()]
            if not labels or not english:raise ValueError("mapped unit needs Japanese and English source labels")
            unit_id=f"{source_id}-POLYGON-{feature_id}"
            record={"unitId":unit_id,"sourcePolygonFeatureId":feature_id,
                "sourceId":source_id,"sourceYear":source_year,"sourceAuthority":source_authority,
                "majorCode":raw.get("majorCode"),"symbol":raw.get("symbol"),
                "sourceLabel":labels[-1]["sourceLabel"],"sourceLabelEnglish":english[-1]["sourceLabelEnglish"],
                "sourceLegendHierarchy":hierarchy,
                "sourceAgeLabel":next((x["sourceLabel"] for x in hierarchy if x["level"]==3),None),
                "sourceAgeLabelEnglish":next((x["sourceLabelEnglish"] for x in hierarchy if x["level"]==3),None),
                "normalizedLabel":english[-1]["sourceLabelEnglish"],
                "normalizationAuthority":source_authority,"vocabularyVersion":vocabulary_version,
                "termStatus":"Unverified","normalizationNote":"Official English source translation retained; controlled-vocabulary normalization pending",
                "numericAgeStatus":"NotResolvedFromNamedSourceInterval",
                "evidenceStatus":"Observed","geometryRole":"MappedSurfacePolygonOnly"}
            previous=units.get(unit_id)
            if previous is not None and previous!=record:raise ValueError("same polygon feature has inconsistent legend attributes")
            units[unit_id]=record;ids.append(unit_id)
        if ids:
            if len(ids)!=2:raise ValueError("mapped unit transition must contain exactly two source polygons")
            pairs.append({"featureId":crossing.get("featureId"),"stationM":crossing.get("stationM"),
                "mappedUnitIdsInRouteOrder":ids,
                "authorizationBoundary":"SurfaceAdjacencyOnly_NoStratigraphicOrder"})
    result={"schemaVersion":"MappedGeologicUnitCatalog-1.0",
        "sourceCrossingSideSha256":side_classification["recordSha256"],
        "unitCount":len(units),"units":sorted(units.values(),key=lambda x:x["sourcePolygonFeatureId"]),
        "transitionCount":len(pairs),"transitions":pairs,
        "realRegionSubsurfaceAuthorized":False,
        "authorizationBoundary":"StableMappedSurfaceUnitIdentity_NoNumericAgeOrSubsurfaceCorrelation"}
    result["recordSha256"]=hashlib.sha256(_canonical(result)).hexdigest();return result
