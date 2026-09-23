"""National, source-preserving evidence index used before regional inference."""
from __future__ import annotations

import math
import re

SCHEMA_VERSION = "JapanNationalGeologicEvidenceIndex-1.0"
SOURCE_TYPES = {"BoreholeLog", "GeologicMap", "MapSheetExplanation",
                "PublishedSection", "Paper", "TerrainModel"}
BASIS_TYPES = {"Observed", "Mapped", "Literature", "DerivedInference"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_national_evidence_record(record):
    required = {"sourceId", "sourceType", "authority", "canonicalUrl", "title",
                "publicationDate", "observationDate", "basisType", "horizontalCrs",
                "horizontalCrsStatus", "verticalDatum", "verticalDatumStatus",
                "coordinateAccuracyM", "bboxLonLat", "geologicalProvince",
                "basinOrTerrane", "ageApplicability", "environmentApplicability",
                "lithologies", "lithologyVocabularyVersion", "artifactSha256",
                "locator", "confidenceDimensions", "exclusions"}
    errors = []
    if not isinstance(record, dict) or not required <= set(record):
        return {"passed": False, "errors": ["IncompleteNationalEvidenceRecord"]}
    for key in ("sourceId", "authority", "canonicalUrl", "title", "publicationDate",
                "basisType", "horizontalCrs", "horizontalCrsStatus", "verticalDatum",
                "verticalDatumStatus", "geologicalProvince", "basinOrTerrane",
                "ageApplicability", "environmentApplicability", "lithologyVocabularyVersion",
                "locator"):
        if not _text(record[key]): errors.append("InvalidText:" + key)
    if record["sourceType"] not in SOURCE_TYPES: errors.append("InvalidSourceType")
    if record["basisType"] not in BASIS_TYPES: errors.append("InvalidBasisType")
    if record["basisType"] == "DerivedInference":
        errors.append("DerivedInferenceCannotEnterEvidenceIndex")
    if not _SHA256.fullmatch(str(record["artifactSha256"])): errors.append("InvalidArtifactSha256")
    accuracy = record["coordinateAccuracyM"]
    if accuracy is not None and (not isinstance(accuracy, (int, float)) or
                                 not math.isfinite(accuracy) or accuracy < 0):
        errors.append("InvalidCoordinateAccuracy")
    bbox = record["bboxLonLat"]
    if (not isinstance(bbox, list) or len(bbox) != 4 or
        not all(isinstance(v, (int, float)) and math.isfinite(v) for v in bbox) or
        bbox[0] > bbox[2] or bbox[1] > bbox[3] or
        not (-180 <= bbox[0] <= bbox[2] <= 180 and -90 <= bbox[1] <= bbox[3] <= 90)):
        errors.append("InvalidBboxLonLat")
    if not isinstance(record["lithologies"], list) or not record["lithologies"]:
        errors.append("MissingLithologies")
    if not isinstance(record["confidenceDimensions"], dict): errors.append("InvalidConfidenceDimensions")
    if not isinstance(record["exclusions"], list): errors.append("InvalidExclusions")
    return {"passed": not errors, "errors": errors}


def build_national_evidence_index(records):
    if not isinstance(records, list): raise ValueError("records must be a list")
    errors=[];seen=set()
    for index,record in enumerate(records):
        audit=validate_national_evidence_record(record)
        errors.extend({"recordIndex":index,"code":code} for code in audit["errors"])
        source_id=record.get("sourceId") if isinstance(record,dict) else None
        if source_id in seen: errors.append({"recordIndex":index,"code":"DuplicateSourceId"})
        seen.add(source_id)
    if errors: raise ValueError("national evidence index rejected: "+str(errors))
    return {"schemaVersion":SCHEMA_VERSION,"recordCount":len(records),"records":records}


def _distance_m(lon1,lat1,lon2,lat2):
    radius=6371008.8
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1);dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return radius*2*math.atan2(math.sqrt(a),math.sqrt(max(0.0,1-a)))


def query_national_evidence(index, target, *, maximum_distance_m=50000.0,
                            source_types=None):
    if not isinstance(index,dict) or index.get("schemaVersion")!=SCHEMA_VERSION:
        raise ValueError("validated national evidence index is required")
    lon=float(target["longitude"]);lat=float(target["latitude"])
    if not (-180<=lon<=180 and -90<=lat<=90): raise ValueError("invalid target coordinate")
    allowed=set(source_types or SOURCE_TYPES);matches=[];rejections=[]
    for record in index["records"]:
        if record["sourceType"] not in allowed:
            rejections.append({"sourceId":record["sourceId"],"reason":"SourceTypeExcluded"});continue
        bbox=record["bboxLonLat"];clon=min(max(lon,bbox[0]),bbox[2]);clat=min(max(lat,bbox[1]),bbox[3])
        distance=_distance_m(lon,lat,clon,clat)
        if distance>maximum_distance_m:
            rejections.append({"sourceId":record["sourceId"],"reason":"OutsideSupportDistance"});continue
        mismatches=[key for key in ("geologicalProvince","ageApplicability","environmentApplicability")
                    if target.get(key) and record[key] not in {target[key],"Unresolved","Multiple"}]
        if mismatches:
            rejections.append({"sourceId":record["sourceId"],"reason":"ApplicabilityMismatch",
                               "fields":mismatches});continue
        matches.append({"sourceId":record["sourceId"],"sourceType":record["sourceType"],
                        "distanceM":distance,"lithologies":record["lithologies"],
                        "geologicalProvince":record["geologicalProvince"],
                        "ageInterval":record["ageApplicability"],
                        "environment":record["environmentApplicability"],
                        "evidenceStatus":record["basisType"],
                        "horizontalCrsStatus":record["horizontalCrsStatus"],
                        "verticalDatumStatus":record["verticalDatumStatus"],
                        "coordinateAccuracyM":record["coordinateAccuracyM"]})
    matches.sort(key=lambda row:(row["distanceM"],row["sourceId"]))
    return {"target":dict(target),"matches":matches,"rejections":rejections,
            "maximumDistanceM":float(maximum_distance_m)}


def borehole_to_national_evidence_record(borehole, *, title, publication_date,
                                         artifact_sha256, locator):
    lon=float(borehole["longitude"]);lat=float(borehole["latitude"])
    lithologies=[]
    for interval in borehole.get("intervals",[]):
        label=interval.get("normalizedLithology") or interval.get("lithology") or interval.get("soilName")
        if _text(label) and label not in lithologies:lithologies.append(label)
    accuracy=borehole.get("horizontalPositionAccuracyM")
    return {"sourceId":borehole["sourceId"],"sourceType":"BoreholeLog",
            "authority":borehole.get("sourceAuthority","MLIT/KuniJiban"),
            "canonicalUrl":borehole["sourceUrl"],"title":title,
            "publicationDate":publication_date,"observationDate":borehole.get("observationDate","Unstated"),
            "basisType":"Observed","horizontalCrs":borehole["horizontalCrs"],
            "horizontalCrsStatus":borehole.get("horizontalCrsStatus","Declared"),
            "verticalDatum":borehole["verticalDatum"],
            "verticalDatumStatus":borehole.get("verticalDatumStatus","Unverified"),
            "coordinateAccuracyM":accuracy,"bboxLonLat":[lon,lat,lon,lat],
            "geologicalProvince":borehole.get("geologicalProvince","Unresolved"),
            "basinOrTerrane":borehole.get("basinOrTerrane","Unresolved"),
            "ageApplicability":borehole.get("ageApplicability","Unresolved"),
            "environmentApplicability":borehole.get("environmentApplicability","Unresolved"),
            "lithologies":lithologies,"lithologyVocabularyVersion":borehole.get("lithologyVocabularyVersion","SourceTerms_Unnormalized"),
            "artifactSha256":artifact_sha256,"locator":locator,
            "confidenceDimensions":{"horizontalCrsStatus":borehole.get("horizontalCrsStatus","Declared"),
              "verticalDatumStatus":borehole.get("verticalDatumStatus","Unverified"),
              "originalObservationPreserved":True},
            "exclusions":["Not a regional prior outside declared support distance"]}
