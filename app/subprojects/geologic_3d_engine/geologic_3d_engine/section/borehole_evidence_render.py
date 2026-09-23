"""Render an observed depth log without laterally interpolating its contacts."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path

from PIL import Image, ImageDraw

from .borehole_evidence import normalize_borehole


_COLORS = ("#d9c29c", "#8a4f32", "#595959", "#bda56d",
           "#454545", "#8b6c52", "#666666", "#c5ad83")


def render_borehole_evidence_section(plan_bundle: Mapping, borehole: Mapping,
                                     station_m: float, output_path,
                                     *, display_depth_m=150.0,
                                     absolute_elevation_authorized=False,
                                     width=1500, height=720):
    """Show terrain and a narrow observed log; never draw lateral contacts."""
    if (not isinstance(plan_bundle, Mapping) or
            plan_bundle.get("schemaVersion") != "PlanEvidenceBundle-1.0"):
        raise ValueError("PlanEvidenceBundle-1.0 is required")
    profile = plan_bundle.get("terrainProfile")
    if not isinstance(profile, Sequence) or len(profile) < 2:
        raise ValueError("terrain profile is required")
    stations = [float(row["stationM"]) for row in profile]
    terrain = [float(row["elevationM"]) for row in profile]
    if (any(not math.isfinite(v) for v in stations+terrain) or
            any(b <= a for a, b in zip(stations, stations[1:]))):
        raise ValueError("terrain profile must be finite and ordered")
    if (isinstance(station_m, bool) or not isinstance(station_m, (int, float)) or
            not math.isfinite(station_m) or not stations[0] <= station_m <= stations[-1]):
        raise ValueError("borehole station lies outside the route")
    if absolute_elevation_authorized is not False:
        raise ValueError("this renderer is restricted to unverified absolute elevation")
    if display_depth_m <= 0:
        raise ValueError("display_depth_m must be positive")
    hole = normalize_borehole(borehole)

    left, right, top, bottom = 90, width-380, 75, height-75
    zmax = max(max(terrain), hole["collarElevationM"]) + 15
    zmin = min(min(terrain), hole["collarElevationM"]-min(display_depth_m,
                                                           hole["totalDepthM"]))-15
    px = lambda s: left+(right-left)*(s-stations[0])/(stations[-1]-stations[0])
    py = lambda z: bottom-(bottom-top)*(z-zmin)/(zmax-zmin)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    terrain_xy = [(px(s), py(z)) for s, z in zip(stations, terrain)]
    unknown = terrain_xy + [(right, bottom), (left, bottom)]
    draw.polygon(unknown, fill="#dddddd")
    draw.line(terrain_xy, fill="#202020", width=3)
    x = px(float(station_m)); half = 9
    rendered = []
    for index, interval in enumerate(hole["intervals"]):
        y0 = py(interval["topElevationM"]); y1 = py(interval["bottomElevationM"])
        draw.rectangle((x-half, y0, x+half, y1), fill=_COLORS[index % len(_COLORS)],
                       outline="#111111")
        rendered.append({"intervalIndex": index,
                         "sourceLabel": interval["sourceLabel"],
                         "normalizedLithology": interval["normalizedLithology"],
                         "termStatus": interval["termStatus"],
                         "topDepthM": interval["topDepthM"],
                         "bottomDepthM": interval["bottomDepthM"]})
        draw.rectangle((right+25, top+index*43, right+39, top+index*43+14),
                       fill=_COLORS[index % len(_COLORS)], outline="#111111")
        draw.text((right+47, top-2+index*43),
                  f"B{index+1} {interval['normalizedLithology']}", fill="#111111")
        draw.text((right+47, top+14+index*43),
                  f"{interval['topDepthM']:g}-{interval['bottomDepthM']:g} m; term {interval['termStatus']}",
                  fill="#444444")
    draw.line((x, py(hole["collarElevationM"])-9, x,
               py(hole["collarElevationM"]-hole["totalDepthM"])+9),
              fill="#000000", width=2)
    draw.text((max(left, x-70), py(hole["collarElevationM"])-28),
              f"{hole['boreholeId']} observed log", fill="#7d0015")
    draw.rectangle((left, top, right, bottom), outline="#000000")
    draw.text((18, 14), "OBSERVED BOREHOLE DEPTH LOG ON CANDIDATE ROUTE", fill="#7d0015")
    draw.text((18, 35),
              "Grey = UNKNOWN SUBSURFACE; no lateral contact interpolation; absolute collar accuracy unverified",
              fill="#202020")
    draw.text((left, bottom+20), "0 m", fill="#111111")
    draw.text((right-75, bottom+20), f"{stations[-1]:.0f} m", fill="#111111")
    path = Path(output_path); path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    record = {
        "schemaVersion": "BoreholeEvidenceSectionRender-1.0",
        "imagePath": str(path), "imageSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "boreholeId": hole["boreholeId"], "stationM": float(station_m),
        "observedIntervalCount": len(rendered), "renderedIntervals": rendered,
        "absoluteElevationStatus": "Unverified_ShownAsReported_NotConstraint",
        "lateralInterpolation": "None",
        "subsurfaceOutsideLog": "Unknown",
        "sectionGeometryAuthorized": False,
        "authorizationBoundary": "DiagnosticEvidenceDisplayOnly_NotLithologyPolygonGeometry",
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    record["recordSha256"] = hashlib.sha256(canonical).hexdigest()
    return record
