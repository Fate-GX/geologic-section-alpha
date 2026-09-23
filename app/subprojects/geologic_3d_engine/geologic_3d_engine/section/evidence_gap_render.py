"""Render what is observed and leave unsupported subsurface explicitly unknown."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from collections.abc import Mapping, Sequence

from PIL import Image, ImageDraw


def render_evidence_gap_section(plan_bundle, readiness, mapped_crossings, path,
                                display_depth_m=150.0, width=1400, height=650):
    if (not isinstance(plan_bundle, Mapping) or
            plan_bundle.get("schemaVersion") != "PlanEvidenceBundle-1.0"):
        raise ValueError("PlanEvidenceBundle-1.0 is required")
    if (not isinstance(readiness, Mapping) or
            readiness.get("schemaVersion") != "RouteEvidenceReadiness-1.0"):
        raise ValueError("RouteEvidenceReadiness-1.0 is required")
    if readiness.get("sectionGeometryAuthorized") is not False:
        raise ValueError("evidence-gap rendering is only for unauthorized geometry")
    if (not isinstance(mapped_crossings, Mapping) or
            mapped_crossings.get("schemaVersion") != "GsjRouteCrossingSideClassification-1.0"):
        raise ValueError("mapped crossing evidence is required")
    if (isinstance(display_depth_m, bool) or not isinstance(display_depth_m, (int, float)) or
            not math.isfinite(display_depth_m) or display_depth_m <= 0):
        raise ValueError("display_depth_m must be positive")
    profile = plan_bundle.get("terrainProfile")
    if (not isinstance(profile, Sequence) or len(profile) < 2 or
            any(not isinstance(row, Mapping) or
                not all(isinstance(row.get(key), (int, float)) and
                        not isinstance(row.get(key), bool) and math.isfinite(row[key])
                        for key in ("stationM", "elevationM")) for row in profile)):
        raise ValueError("complete finite terrain profile is required")
    stations = [float(row["stationM"]) for row in profile]
    terrain = [float(row["elevationM"]) for row in profile]
    if any(b <= a for a, b in zip(stations, stations[1:])):
        raise ValueError("terrain stations must strictly increase")
    transitions = [row for row in mapped_crossings.get("crossings", [])
                   if row.get("sideClassificationStatus") == "MappedUnitTransition"]
    if any(not isinstance(row.get("stationM"), (int, float)) or
           not stations[0] <= row["stationM"] <= stations[-1] for row in transitions):
        raise ValueError("mapped transition lies outside the route")

    left, right, top, bottom = 90, width-35, 65, height-70
    zmax = max(terrain) + 0.08*display_depth_m
    zmin = min(terrain) - float(display_depth_m)
    px = lambda station: left+(right-left)*(station-stations[0])/(stations[-1]-stations[0])
    py = lambda elevation: bottom-(bottom-top)*(elevation-zmin)/(zmax-zmin)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    unknown = [(px(s), py(z)) for s, z in zip(stations, terrain)] + [
        (px(stations[-1]), py(zmin)), (px(stations[0]), py(zmin))]
    draw.polygon(unknown, fill="#d9d9d9")
    # Keep the fill neutral rather than using a geological lithology pattern.
    terrain_points = [(px(s), py(z)) for s, z in zip(stations, terrain)]
    draw.line(terrain_points, fill="#202020", width=3)
    for index, event in enumerate(transitions, 1):
        x = px(float(event["stationM"]))
        z = float(event.get("terrainElevationM", terrain[min(range(len(stations)),
            key=lambda i: abs(stations[i]-event["stationM"]))]))
        y = py(z)
        draw.line((x, y-12, x, y+12), fill="#0066cc", width=3)
        draw.text((x+3, y-25), f"M{index}", fill="#004c99")
    for hole in readiness.get("currentRouteBoreholes", []):
        if hole.get("projectionState") != "Rejected" or not isinstance(hole.get("stationM"), (int, float)):
            continue
        x = px(float(hole["stationM"]))
        nearest = min(range(len(stations)), key=lambda i: abs(stations[i]-hole["stationM"]))
        y = py(terrain[nearest])-22
        draw.line((x-6, y-6, x+6, y+6), fill="#b00020", width=2)
        draw.line((x-6, y+6, x+6, y-6), fill="#b00020", width=2)
        label = f"{hole.get('boreholeId','hole')} rejected ({hole.get('projectionDistanceM',0):.0f} m off)"
        label_x = x+9 if x < (left+right)/2 else x-205
        draw.text((label_x, y-19), label, fill="#8b0018")
    draw.rectangle((left, top, right, bottom), outline="black")
    draw.text((18, 14), "EVIDENCE GAP SECTION - OBSERVED TERRAIN AND MAPPED SURFACE CONTACTS ONLY",
              fill="#8b0018")
    draw.text((18, 34),
              f"Grey field = UNKNOWN SUBSURFACE; display depth {display_depth_m:g} m is viewport only",
              fill="#202020")
    draw.text((left, bottom+18), "0 m", fill="black")
    draw.text((right-70, bottom+18), f"{stations[-1]:.0f} m", fill="black")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    record = {
        "schemaVersion": "EvidenceGapSectionRender-1.0",
        "imagePath": str(output), "imageSha256": digest,
        "routeLengthM": stations[-1]-stations[0],
        "displayDepthM": float(display_depth_m),
        "displayDepthMeaning": "ViewportOnly_NotEvidenceOfInvestigationDepth",
        "mappedSurfaceTransitionCount": len(transitions),
        "directConstraintStationCount": readiness.get("constraintStationDistribution", {}).get(
            "constraintStationCount", 0),
        "subsurfaceState": "Unknown_NoAuthorizedGeometry",
        "authorizationBoundary": "MustNotBeUsedAsLithologyGeometry",
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    record["recordSha256"] = hashlib.sha256(canonical).hexdigest()
    return record
