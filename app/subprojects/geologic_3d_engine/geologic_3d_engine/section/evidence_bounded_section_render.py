"""Render evidence-bounded lithology intervals without bridging unknown gaps."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from PIL import Image, ImageDraw


def _runs(rows):
    result = []; start = None
    for index, row in enumerate(rows + [None]):
        supported = row is not None and row.get("coverageStatus") == "BoundedByEvidence"
        if supported and start is None:
            start = index
        elif not supported and start is not None:
            result.append((start, index - 1)); start = None
    return result


def render_evidence_bounded_section(section: Mapping, unit_styles: Mapping, path,
                                    *, width=1400, height=700, display_floor_m=None):
    if section.get("schemaVersion") != "EvidenceBoundedLithologySection-1.0":
        raise ValueError("EvidenceBoundedLithologySection-1.0 is required")
    stations = section["stationsM"]; terrain = section["terrainElevationM"]
    if len(stations) < 2:
        raise ValueError("at least two section samples are required")
    finite_boundaries = [value for unit in section["unitsBottomUp"] for row in unit["samples"]
                         for value in (row["bottomElevationM"], row["topElevationM"])
                         if value is not None]
    zmax = max(terrain)
    zmin = (float(display_floor_m) if display_floor_m is not None
            else min(finite_boundaries + terrain) - 0.08 * max(zmax - min(finite_boundaries + terrain), 1))
    if zmin >= zmax:
        raise ValueError("display floor must lie below terrain")
    left, right, top, bottom = 90, width - 35, 70, height - 75
    px = lambda station: left + (right-left)*(station-stations[0])/(stations[-1]-stations[0])
    py = lambda elevation: bottom - (bottom-top)*(elevation-zmin)/(zmax-zmin)
    image = Image.new("RGB", (width, height), "white"); draw = ImageDraw.Draw(image)
    unknown = [(px(s), py(z)) for s, z in zip(stations, terrain)] + [
        (px(stations[-1]), py(zmin)), (px(stations[0]), py(zmin))]
    draw.polygon(unknown, fill="#d6d6d6")
    render_audit = []
    for unit in section["unitsBottomUp"]:
        style = unit_styles.get(unit["unitId"])
        if (not isinstance(style, Mapping) or not isinstance(style.get("fillHex"), str)
                or not isinstance(style.get("displayLabel"), str)):
            raise ValueError("every unit requires an explicit fillHex and displayLabel")
        runs = _runs(unit["samples"])
        polygons = 0; isolated = 0
        for first, last in runs:
            rows = unit["samples"][first:last+1]
            if len(rows) < 2:
                isolated += 1
                x = px(rows[0]["stationM"])
                draw.line((x, py(rows[0]["bottomElevationM"]),
                           x, py(rows[0]["topElevationM"])), fill=style["fillHex"], width=5)
                continue
            polygon = [(px(row["stationM"]), py(row["topElevationM"])) for row in rows]
            polygon += [(px(row["stationM"]), py(row["bottomElevationM"]))
                        for row in reversed(rows)]
            draw.polygon(polygon, fill=style["fillHex"], outline="#333333")
            polygons += 1
        render_audit.append({"unitId": unit["unitId"], "supportedRunCount": len(runs),
                             "polygonCount": polygons, "isolatedSampleMarkerCount": isolated})
    draw.line([(px(s), py(z)) for s, z in zip(stations, terrain)], fill="#111111", width=3)
    draw.rectangle((left, top, right, bottom), outline="#111111")
    draw.text((18, 14), "EVIDENCE-BOUNDED LITHOLOGY SECTION", fill="#111111")
    draw.text((18, 34), "Grey = UNKNOWN; coloured intervals exist only where both boundaries are supported",
              fill="#333333")
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True); image.save(output)
    record = {"schemaVersion": "EvidenceBoundedSectionRender-1.0",
              "imagePath": str(output),
              "imageSha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "unitRenderAudit": render_audit,
              "unknownColour": "#d6d6d6", "unknownGapBridgingUsed": False,
              "curveSmoothingUsed": False,
              "realRegionAuthorization": section["realRegionAuthorization"]}
    record["recordSha256"] = hashlib.sha256(json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    return record
