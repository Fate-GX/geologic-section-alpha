"""Enrich a bounded KuniJiban marker index with XML header metadata."""
from __future__ import annotations
import hashlib,json,math,re
import xml.etree.ElementTree as ET

from ..section.bed0500_xml import MAXIMUM_XML_BYTES,_decode_xml,_number,_required_text


def extract_candidate_metadata(raw):
    if not isinstance(raw,bytes) or not raw or len(raw)>MAXIMUM_XML_BYTES:
        raise ValueError("BED XML metadata response size is invalid")
    text=_decode_xml(raw)
    if re.search(r"<!\s*(?:ENTITY|ATTLIST)\b",text,re.IGNORECASE):
        raise ValueError("BED XML entities and attribute declarations are prohibited")
    text=re.sub(r"^\ufeff?<\?xml[^>]*\?>","",text,count=1,flags=re.IGNORECASE)
    text=re.sub(r"<!DOCTYPE[^>]*>","",text,count=1,flags=re.IGNORECASE)
    try:root=ET.fromstring(text)
    except ET.ParseError as exc:raise ValueError("BED XML metadata is not well formed") from exc
    version=root.attrib.get("DTD_version")
    if root.tag!="ボーリング情報" or version not in {"2.10","3.00","4.00","5.00"}:
        raise ValueError("unsupported BED XML metadata version")
    total_tag="総削孔長" if version in {"4.00","5.00"} else "総掘進長"
    name_nodes=[(node.text or "").strip() for node in root.findall(".//ボーリング名")]
    if len(name_nodes)>1:
        raise ValueError("BED XML metadata borehole name is duplicated")
    result={
        "dtdVersion":version,
        "boreholeName":name_nodes[0] if name_nodes and name_nodes[0] else None,
        "totalDepthM":_number(_required_text(root,total_tag),"total depth"),
        "collarElevationM":_number(_required_text(root,"孔口標高"),"collar elevation"),
        "formatGeodeticSystemCode":_required_text(root,"測地系"),
        "sourceXmlSha256":hashlib.sha256(raw).hexdigest(),
        "sourceXmlByteLength":len(raw),
    }
    for output,tag in (("coordinateAcquisitionMethodCode","取得方法コード"),
                       ("coordinateReadingPrecisionCode","読取精度コード")):
        nodes=[(node.text or "").strip() for node in root.iter(tag)]
        result[output]=nodes[0] if len(nodes)==1 and nodes[0] else None
    if version in {"3.00","4.00"}:
        method=result["coordinateAcquisitionMethodCode"]
        precision=result["coordinateReadingPrecisionCode"]
        result["coordinateMethodClass"]={"01":"SurveyIncludingGPS","02":"TopographicMapReading",
            "03":"StandaloneGPS","09":"OtherOrUnknown"}.get(method,"Unresolved")
        result["declaredResolutionArcSeconds"]={"0":1.0,"1":0.1,"2":0.01,
            "3":0.001,"4":0.0001}.get(precision)
        geodetic=result["formatGeodeticSystemCode"]
        if version=="4.00":
            result["formatHorizontalCrs"]={"00":"TokyoDatum","01":"EPSG:4612",
                "02":"EPSG:6668"}.get(geodetic,"Unresolved")
        else:
            result["formatHorizontalCrs"]={"0":"TokyoDatum","1":"EPSG:4612"}.get(
                geodetic,"Unresolved")
    else:
        result["coordinateMethodClass"]="VersionSpecificCodeReviewRequired"
        result["declaredResolutionArcSeconds"]=None
        result["formatHorizontalCrs"]="VersionSpecificCodeReviewRequired"
    result["metadataStatus"]="ParsedSupportedBEDVersion"
    return result


def inspect_candidate_metadata(raw):
    """Keep a hash-bound rejection row when one candidate uses another format."""
    try:return extract_candidate_metadata(raw)
    except ValueError as error:
        match=re.search(br'DTD_version=["\x27]([^"\x27]+)',raw[:4096]) if isinstance(raw,bytes) else None
        return {"metadataStatus":"RejectedUnsupportedOrMalformed",
          "detectedDtdVersion":match.group(1).decode("ascii","replace") if match else None,
          "sourceXmlSha256":hashlib.sha256(raw).hexdigest() if isinstance(raw,bytes) else None,
          "sourceXmlByteLength":len(raw) if isinstance(raw,bytes) else None,
          "rejectionReason":str(error),"coordinateMethodClass":"Unavailable",
          "declaredResolutionArcSeconds":None,"totalDepthM":0.0}


def _distance_bucket(distance):
    for index,limit in enumerate((500.0,1000.0,2000.0,5000.0)):
        if distance<=limit:return index
    return 4


def build_ranked_candidate_metadata(candidate_index,responses):
    if candidate_index.get("schemaVersion")!="KuniJibanRouteCandidateIndex-1.0":
        raise ValueError("candidate index schema is invalid")
    claimed=candidate_index.get("recordSha256")
    unsigned={key:value for key,value in candidate_index.items() if key!="recordSha256"}
    actual=hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),
        ensure_ascii=False).encode()).hexdigest()
    if claimed!=actual:raise ValueError("candidate index hash mismatch")
    candidates=candidate_index.get("candidates")
    if not isinstance(candidates,list) or not candidates:
        raise ValueError("candidate index is empty")
    response_map={int(record_id):raw for record_id,raw in responses}
    if len(response_map)!=len(responses):raise ValueError("duplicate metadata response ID")
    expected={int(row["providerRecordId"]) for row in candidates}
    if len(expected)!=len(candidates):raise ValueError("candidate index has duplicate record IDs")
    if set(response_map)!=expected:raise ValueError("metadata responses do not match candidate index")
    rows=[]
    method_tier={"SurveyIncludingGPS":0,"StandaloneGPS":1,"TopographicMapReading":2,
                 "OtherOrUnknown":3,"Unresolved":4,"VersionSpecificCodeReviewRequired":5,
                 "Unavailable":6}
    for marker in candidates:
        identifier=int(marker["providerRecordId"]);metadata=inspect_candidate_metadata(response_map[identifier])
        distance=float(marker["projectionDistanceM"])
        resolution=metadata["declaredResolutionArcSeconds"]
        key=[_distance_bucket(distance),method_tier[metadata["coordinateMethodClass"]],
             resolution if resolution is not None else math.inf,-metadata["totalDepthM"],distance,identifier]
        rows.append({**marker,"xmlMetadata":metadata,"screeningPriorityKey":key,
          "screeningOnly":True,"sectionConstraintAuthorized":False})
    rows.sort(key=lambda row:tuple(row["screeningPriorityKey"]))
    if not any(row["xmlMetadata"]["metadataStatus"]=="ParsedSupportedBEDVersion" for row in rows):
        raise ValueError("no candidate metadata could be parsed")
    result={"schemaVersion":"KuniJibanRankedCandidateMetadata-1.0",
      "candidateIndexCanonicalSha256":hashlib.sha256(json.dumps(candidate_index,sort_keys=True,
        separators=(",",":"),ensure_ascii=False).encode()).hexdigest(),
      "rankingPolicy":"DistanceBucket_ThenCoordinateMethod_ThenDeclaredResolution_ThenDepth_ThenDistance",
      "distanceBucketsM":[500,1000,2000,5000],"candidateCount":len(rows),"candidates":rows,
      "parsedCandidateCount":sum(row["xmlMetadata"]["metadataStatus"]=="ParsedSupportedBEDVersion" for row in rows),
      "rejectedMetadataCount":sum(row["xmlMetadata"]["metadataStatus"]!="ParsedSupportedBEDVersion" for row in rows),
      "authorizationBoundary":"DiscoveryRankingOnly_NoBoreholeOrSectionAuthorization"}
    canonical=json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    result["recordSha256"]=hashlib.sha256(canonical).hexdigest()
    return result
