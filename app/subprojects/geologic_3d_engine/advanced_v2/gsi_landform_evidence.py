from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import urllib.error
import urllib.request


ZOOM = 14
NATURAL_URL = "https://cyberjapandata.gsi.go.jp/xyz/experimental_landformclassification1/{z}/{x}/{y}.geojson"
ARTIFICIAL_URL = "https://cyberjapandata.gsi.go.jp/xyz/experimental_landformclassification2/{z}/{x}/{y}.geojson"
SOURCE_ID = "GSI-LANDFORM-VECTOR-2026"

_GROUPS = {
    "MountainousRelief": {10101,11201,11202,11203,11204,1010101,10202,10204,2010201},
    "RollingHills": {10301,10302,10303,10304,10305,10306,10307,10308,10310,10312,10314,10508,2010101},
    "MountainFrontPiedmont": {10401,10402,10403,10404,10406,10407,3010101,10501,10502,3020101},
    "CoastalLowland": {10504,10505,10512,3050101,10702,10705,10806},
    "BroadLowland": {10503,10506,10507,10601,10701,10703,10704,10801,10804,
                     2010301,3030101,3030201,3040101,3040201,3040202},
    "ArtificiallyModifiedOrUnresolved": {11001,11002,11003,11004,11005,11006,11007,
                                          11008,11009,11010,11011,11014,
                                          4010101,4010201,4010301},
}


def class_for_code(code):
    try:
        value = int(code)
    except (TypeError, ValueError):
        return "Unresolved"
    for name, values in _GROUPS.items():
        if value in values:
            return name
    return "Unresolved"


def _tile(longitude, latitude, zoom=ZOOM):
    scale = 2 ** zoom
    x = int((longitude + 180.0) / 360.0 * scale)
    latitude = max(-85.05112878, min(85.05112878, latitude))
    y = int((1.0 - math.asinh(math.tan(math.radians(latitude))) / math.pi) * 0.5 * scale)
    return x, y


def _inside_ring(longitude, latitude, ring):
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(current[0]), float(current[1])
        if (y1 > latitude) != (y2 > latitude):
            crossing = (x2-x1) * (latitude-y1) / (y2-y1) + x1
            if longitude < crossing:
                inside = not inside
        previous = current
    return inside


def _inside_geometry(longitude, latitude, geometry):
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    polygons = [coordinates] if kind == "Polygon" else coordinates if kind == "MultiPolygon" else []
    for polygon in polygons:
        if polygon and _inside_ring(longitude, latitude, polygon[0]) and not any(
                _inside_ring(longitude, latitude, hole) for hole in polygon[1:]):
            return True
    return False


def _download_json(url, path):
    if path.is_file():
        data = path.read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent":"geologic-3d-engine-research/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.with_suffix(".missing").write_text("HTTP 404\n", encoding="ascii")
                return None, None
            raise
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    return json.loads(data.decode("utf-8")), hashlib.sha256(data).hexdigest()


def acquire_landform_evidence(terrain_profile, cache_directory):
    cache = Path(cache_directory)
    tile_cache = {}
    hashes = {}
    records = []
    for row in terrain_profile:
        longitude = float(row["longitude"]); latitude = float(row["latitude"])
        x, y = _tile(longitude, latitude)
        matches = []
        for layer, template in (("natural", NATURAL_URL), ("artificial", ARTIFICIAL_URL)):
            key = (layer, x, y)
            if key not in tile_cache:
                path = cache / f"landform_{layer}" / str(ZOOM) / str(x) / f"{y}.geojson"
                tile_cache[key] = _download_json(template.format(z=ZOOM,x=x,y=y), path)
            collection, digest = tile_cache[key]
            if digest:
                hashes[f"{layer}/{ZOOM}/{x}/{y}"] = digest
            if collection:
                for feature in collection.get("features", []):
                    if _inside_geometry(longitude, latitude, feature.get("geometry", {})):
                        properties = feature.get("properties", {})
                        code = properties.get("code")
                        matches.append({"layer":layer, "code":code,
                                        "class":class_for_code(code),
                                        "properties":properties})
        # Artificial evidence is retained alongside natural evidence and wins
        # only in the downstream ranked-hypothesis classifier.
        records.append({"stationM":float(row["stationM"]), "longitude":longitude,
                        "latitude":latitude, "sourceId":SOURCE_ID,
                        "matches":matches, "coverageStatus":"Matched" if matches else "NoCoverage"})
    flattened = [{"stationM":row["stationM"], "sourceId":SOURCE_ID,
                  "code":match["code"], "class":match["class"], "layer":match["layer"]}
                 for row in records for match in row["matches"]]
    return {"sourceId":SOURCE_ID, "canonicalUrls":[NATURAL_URL, ARTIFICIAL_URL],
            "zoom":ZOOM, "samples":records, "tileSha256":hashes,
            "classificationEvidence":flattened,
            "inferenceBoundary":"LandformPriorOnly_NoSubsurfaceContactAuthorization"}
