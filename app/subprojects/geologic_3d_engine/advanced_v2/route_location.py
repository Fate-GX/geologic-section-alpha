"""Source-bound endpoint names; partial addresses never become invented addresses."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from terrain_morphology import classify_terrain_morphology

MUNICIPALITIES_URL="https://maps.gsi.go.jp/js/muni.js"
GEOCODER_URL="https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress"
_MUNICIPALITY_CACHE=None
TERRAIN_NAMES={"MountainousRelief":"山間部","RollingHills":"丘陵部",
    "BroadLowland":"平坦地","NarrowValleyOrGorge":"谷地形",
    "MountainFrontPiedmont":"山麓部","CoastalLowland":"海岸低地"}


def fetch_bytes(url):
    request=urllib.request.Request(url,headers={"User-Agent":"geologic-3d-engine-research/1.0"})
    with urllib.request.urlopen(request,timeout=6) as response:return response.read()


def parse_municipalities(data):
    result={}
    for code,value in re.findall(r'GSI\.MUNI_ARRAY\["(\d+)"\]\s*=\s*\x27([^\x27]*)\x27',data.decode("utf-8-sig")):
        fields=value.split(",")
        if len(fields)==4 and fields[0].isdigit():
            result[code.zfill(5)]={"prefectureCode":fields[0].zfill(2),
                "prefecture":fields[1],"municipality":fields[3].replace("　","")}
    if not result:raise ValueError("GSI municipality table unavailable")
    return result


def _clean(value):
    # Addresses are data, never CAD commands/control strings.
    return " ".join(str(value or "").replace("\\"," ").split())[:256]


def place_label(record,terrain):
    prefix="".join(_clean(record.get(k)) for k in ("prefecture","municipality"))
    detail=_clean(record.get("detail"))
    if detail:
        return (prefix or "行政区未取得 ")+detail
    name=TERRAIN_NAMES.get(terrain.get("primaryClass"))
    confidence=terrain.get("confidenceClass")
    if name and confidence in {"EvidenceSupported","ShapeSupported"}:
        source="地形資料" if confidence=="EvidenceSupported" else "DEM形状"
        return (prefix+" " if prefix else "地名未取得 ")+f"{name}（{source}からの判定・詳細地名未取得）"
    return (prefix+" " if prefix else "地名未取得 ")+"（詳細地名未取得・地形区分未確定）"


def _local_terrain(profile,index):
    if len(profile)<3:return {}
    endpoint=float(profile[0 if index==0 else -1]["stationM"])
    rows=[row for row in profile if abs(float(row["stationM"])-endpoint)<=500]
    if len(rows)<3:return {}
    return classify_terrain_morphology([r["stationM"] for r in rows],[r["elevationM"] for r in rows])


def resolve_route_locations(route,profile,*,fetch=fetch_bytes):
    global _MUNICIPALITY_CACHE
    acquired=datetime.now(timezone.utc).isoformat();table={};table_digest=None;table_error=None
    try:
        if fetch is fetch_bytes and _MUNICIPALITY_CACHE and time.monotonic()-_MUNICIPALITY_CACHE[0]<86400:
            _,table,table_digest=_MUNICIPALITY_CACHE
        else:
            raw=fetch(MUNICIPALITIES_URL);table=parse_municipalities(raw)
            table_digest=hashlib.sha256(raw).hexdigest()
            if fetch is fetch_bytes:_MUNICIPALITY_CACHE=(time.monotonic(),table,table_digest)
    except Exception as error:table_error=type(error).__name__
    records=[]
    for index,(longitude,latitude) in enumerate(route):
        url=GEOCODER_URL+"?"+urllib.parse.urlencode({"lat":latitude,"lon":longitude})
        record={"endpoint":"AB"[index],"longitude":longitude,"latitude":latitude,
                "prefecture":"","municipality":"","detail":"","acquiredUtc":acquired,
                "sourceUrl":url,"municipalitySourceUrl":MUNICIPALITIES_URL,
                "municipalityTableSha256":table_digest,"coordinateInterpretation":"SelectedMapLonLat_NotSurveyed"}
        if table_error:record["municipalityTableError"]=table_error
        try:
            raw=fetch(url);result=json.loads(raw).get("results") or {}
            record["responseSha256"]=hashlib.sha256(raw).hexdigest();record["rawResult"]=result
            code=str(result.get("muniCd", ""));code=code.zfill(5) if code.isdigit() else ""
            record["municipalityCode"]=code
            if code in table:record.update(table[code])
            elif code:
                # A valid administrative code prefix can preserve a prefecture
                # even when the municipality row is absent. No nearest-place fallback.
                record["prefecture"]=next((r["prefecture"] for r in table.values() if r["prefectureCode"]==code[:2]),"")
            record["detail"]=_clean(result.get("lv01Nm"))
        except Exception as error:record["lookupError"]=type(error).__name__
        record["terrainContext"]=_local_terrain(profile,index)
        record["displayName"]=place_label(record,record["terrainContext"])
        record["status"]="Complete" if all(record[k] for k in ("prefecture","municipality","detail")) else "PartialOrUnavailable"
        records.append(record)
    return {"schemaVersion":"RouteEndpointLocation-1.0","sourceIds":["GSI-REVERSE-GEOCODER","GSI-MUNICIPALITY-TABLE"],"endpoints":records}


def annotation_lines(locations):
    lines=[]
    for row in locations.get("endpoints",[]):
        lines.append(f"{row['endpoint']}  LAT {row['latitude']:.8f} N / LON {row['longitude']:.8f} E")
        name="  "+row["displayName"]
        lines.extend(name[i:i+80] for i in range(0,len(name),80))
    return lines
