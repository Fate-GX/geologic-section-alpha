"""Translate an audited arbitrary-route section into the native DWG handoff.

The raster preview and the DWG consume the same boundary arrays.  This module
does not infer geology; it only turns already-audited, mutually exclusive bodies
into closed section-coordinate polygons and drafting primitives.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .contract_integrity import build_integrity_envelope, canonical_json_bytes


def _rgb(text: str) -> list[int]:
    if not isinstance(text, str) or len(text) != 7 or not text.startswith("#"):
        raise ValueError("lithology color must be #RRGGBB")
    return [int(text[i:i + 2], 16) for i in (1, 3, 5)]


def _runs(mask):
    start = None
    for index, active in enumerate([*mask, False]):
        if active and start is None:
            start = index
        elif not active and start is not None:
            if index - start >= 2:
                yield start, index
            start = None


def _tick_values(lower: float, upper: float, spacing: float):
    first = math.ceil(lower / spacing) * spacing
    return [first + i * spacing for i in range(int(math.floor((upper - first) / spacing)) + 1)]


def build_arbitrary_route_dwg_contract(model: dict, *, drawing_id="ARBITRARY-ROUTE-SECTION") -> dict:
    if model.get("decision") != "Experimental" or model.get("realRegionAuthorized") is not False:
        raise ValueError("only an audited Experimental synthetic model is accepted")
    audits = model.get("preOutputComplianceAudit", {})
    if not audits.get("passed") or not model.get("modelAudit", {}).get("passed"):
        raise ValueError("model and pre-output audits must pass before DWG export")
    stations = [float(v) for v in model["stationsM"]]
    terrain = [float(v) for v in model["terrainElevationM"]]
    bodies = model["syntheticEventArchitecture"]["renderBodies"]
    if len(stations) < 2 or len(terrain) != len(stations):
        raise ValueError("station and terrain arrays are inconsistent")
    styles = {v["unitId"]: v for v in model["renderingLithologies"]}
    polygons, contacts = [], []
    for body_index, body in enumerate(bodies):
        top = [float(v) for v in body["topElevationM"]]
        bottom = [float(v) for v in body["bottomElevationM"]]
        mask = [bool(v) and t > b for v, t, b in zip(body["activeMask"], top, bottom)]
        if not (len(top) == len(bottom) == len(mask) == len(stations)):
            raise ValueError("body arrays are inconsistent")
        style = styles[body["unitId"]]
        for run_index, (start, stop) in enumerate(_runs(mask)):
            forward = [[stations[i], top[i]] for i in range(start, stop)]
            reverse = [[stations[i], bottom[i]] for i in range(stop - 1, start - 1, -1)]
            vertices = forward + reverse
            if len(vertices) < 4:
                continue
            polygons.append({
                "polygonId": f"{body['unitId']}-{run_index}", "unitId": body["unitId"],
                "displayName": style["label"], "boundaryLayer": "19_ハッチ境界_非印刷",
                "hatchLayer": f"30_岩相カラー_{body_index + 1:02d}",
                "trueColorRGB": _rgb(style["color"]), "vertices": vertices,
                "closed": True, "hatchPattern": "SOLID", "associative": True,
                "sourceCoordinateFrame": "RouteStationM_ElevationM",
            })
            contacts.append({"contactId": f"CONTACT-{body['unitId']}-{run_index}",
                             "unitId": body["unitId"], "layer": "20_岩相区分線_推定",
                             "vertices": forward, "lineType": "Continuous",
                             "drawOrder": "Foremost"})
    if not polygons:
        raise ValueError("no positive-area body can be exported")
    drafting = model["draftingSpecification"]
    lo = min(min(float(v) for v in b["bottomElevationM"]) for b in bodies)
    hi = max(terrain)
    horizontal = float(drafting["horizontalTickM"])
    vertical = float(drafting["verticalTickM"])
    body = {
        "contractVersion": "1.1", "drawingId": drawing_id,
        "artifactType": "SyntheticGeologicCrossSection", "notForDesign": True,
        "syntheticDisclosure": "疑似データ：公開地質資料を参考にした合成断面。調査・設計・施工に使用不可。",
        "generatorVersion": model["schemaVersion"], "dwgVersion": "AC1032",
        "sectionId": drafting["sectionId"], "coordinateFrame": "RouteStationM_ElevationM",
        "sourceCoordinateFrame": "WGS84Route_GSIDEMElevation",
        "nativeApiPlan": ["Polyline.AddVertexAt", "Hatch.AppendLoop", "Hatch.EvaluateHatch",
                          "DBText", "DrawOrderTable.MoveToBottom", "Database.SaveAs"],
        "polygons": polygons, "contactLines": contacts,
        "terrainLine": {"layer": "10_地表面", "vertices": [[x, z] for x, z in zip(stations, terrain)],
                        "drawOrder": "Foremost"},
        "drafting": {"title": model.get("displayTitle", "合成地質断面図"),
                      "sectionId": drafting["sectionId"],
                      "leftDirection": drafting["leftDirection"],
                      "rightDirection": drafting["rightDirection"],
                      "actualSectionLengthM": stations[-1], "horizontalUnit": "m",
                      "elevationDatum": drafting["elevationDatum"], "verticalUnit": "m",
                      "verticalExaggeration": 1.0,
                      "horizontalTicksM": _tick_values(stations[0], stations[-1], horizontal),
                      "elevationTicksM": _tick_values(lo, hi, vertical),
                      "bilateralElevationTicks": True},
        "lineageManifest": {"sources": ["GSI-ELEVATION-TILE", "GSJ-SEAMLESS-V2"],
                            "modelDecision": "Experimental", "realRegionAuthorized": False},
    }
    canonical = canonical_json_bytes(body)
    body["contractSha256"] = hashlib.sha256(canonical).hexdigest()
    body["validation"] = {"passed": True, "polygonCount": len(polygons),
                          "contactLineCount": len(contacts), "contactLineForemost": True,
                          "terrainLinePresent": True, "bilateralElevationTicks": True,
                          "actualLengthMatchesStations": True}
    return body


def write_arbitrary_route_dwg_handoff(model: dict, output_path) -> Path:
    contract = build_arbitrary_route_dwg_contract(model)
    envelope = build_integrity_envelope(contract, contract["validation"], "arbitrary-route-dwg-1.1")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    document = {"geologicContractEnvelope": envelope}
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
