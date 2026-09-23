"""Render off-route boreholes as context without creating section contacts."""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .borehole_evidence import normalize_borehole


def _font(size):
    path = Path("C:/Windows/Fonts/meiryo.ttc")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def _pair(value, name):
    if (not isinstance(value, list) or len(value) != 2 or
            any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                not math.isfinite(v) for v in value)):
        raise ValueError(f"{name} must be a finite longitude/latitude pair")
    return [float(value[0]), float(value[1])]


def render_regional_borehole_context(plan: Mapping, roles: Mapping,
                                     borehole_collection: Mapping, image_path,
                                     *, width=1400, height=850):
    """Create a plan-location and relative-depth log diagnostic.

    The borehole column is intentionally detached from the section station and
    uses depth below collar only. No interval elevation becomes section geometry.
    """
    if width < 900 or height < 600:
        raise ValueError("regional context canvas is too small")
    if plan.get("schemaVersion") != "PlanEvidenceBundle-1.0":
        raise ValueError("PlanEvidenceBundle-1.0 is required")
    if roles.get("schemaVersion") != "BoreholeRouteRoleClassification-1.0":
        raise ValueError("route-role classification is required")
    route = [_pair(p, "route vertex") for p in plan.get("routeLonLat", [])]
    if len(route) < 2:
        raise ValueError("plan route requires at least two vertices")
    holes = borehole_collection.get("boreholes")
    if not isinstance(holes, list) or not holes:
        raise ValueError("normalized borehole collection is required")
    by_source = {h.get("sourceId"): normalize_borehole(h) for h in holes}
    selected = []
    for role in roles.get("boreholes", []):
        if (role.get("role") != "RegionalContextOnly" or
                role.get("contextMayBeDisplayed") is not True or
                role.get("sectionGeometryAuthorized") is not False or
                role.get("contextDisplayBoundary") !=
                "LocationAndSourceSummaryOnly_NoProjectedContacts"):
            continue
        hole = by_source.get(role.get("sourceId"))
        if hole is None or hole["boreholeId"] != role.get("boreholeId"):
            raise ValueError("route role is not bound to a borehole record")
        source_xy = _pair(role.get("sourceLonLat"), "source location")
        if max(abs(source_xy[i]-[hole["longitude"], hole["latitude"]][i])
               for i in range(2)) > 1e-12:
            raise ValueError("route role source coordinate mismatch")
        nearest = _pair(role.get("nearestRouteLonLat"), "nearest route point")
        selected.append((role, hole, source_xy, nearest))
    if not selected:
        raise ValueError("no displayable regional-context borehole exists")

    image = Image.new("RGB", (width, height), "#f7f4ed")
    draw = ImageDraw.Draw(image)
    title, body, small = _font(28), _font(18), _font(15)
    draw.text((35, 24), "地域参考ボーリング — 位置と柱状概要", fill="#18232d", font=title)
    draw.text((35, 65), "断面拘束には未使用 / 接触線を生成しません", fill="#a12424", font=body)
    map_box = (35, 110, int(width*.59), height-55)
    draw.rectangle(map_box, fill="#e9eef1", outline="#53636d", width=2)
    points = route + [item[2] for item in selected]
    lon_min, lon_max = min(p[0] for p in points), max(p[0] for p in points)
    lat_min, lat_max = min(p[1] for p in points), max(p[1] for p in points)
    pad_lon = max((lon_max-lon_min)*.08, 1e-5)
    pad_lat = max((lat_max-lat_min)*.08, 1e-5)
    lon_min -= pad_lon; lon_max += pad_lon; lat_min -= pad_lat; lat_max += pad_lat
    def xy(p):
        x = map_box[0]+20+(map_box[2]-map_box[0]-40)*(p[0]-lon_min)/(lon_max-lon_min)
        y = map_box[3]-20-(map_box[3]-map_box[1]-40)*(p[1]-lat_min)/(lat_max-lat_min)
        return x, y
    draw.line([xy(p) for p in route], fill="#1769aa", width=5)
    draw.text((map_box[0]+12, map_box[1]+10), "元測線", fill="#1769aa", font=body)
    for role, hole, source_xy, nearest in selected:
        hp, rp = xy(source_xy), xy(nearest)
        draw.line([hp, rp], fill="#a44a8b", width=2)
        r = 8
        draw.ellipse((hp[0]-r, hp[1]-r, hp[0]+r, hp[1]+r),
                     fill="#d72f8a", outline="white", width=2)
        draw.text((hp[0]+12, hp[1]-12),
                  f"{hole['boreholeId']}  離隔 {role['projectionDistanceM']:.0f} m",
                  fill="#66113e", font=small)

    role, hole, _, _ = selected[0]
    panel = (int(width*.63), 110, width-35, height-55)
    draw.rectangle(panel, fill="white", outline="#53636d", width=2)
    draw.text((panel[0]+18, panel[1]+14), f"{hole['boreholeId']}  深度柱状（相対表示）",
              fill="#18232d", font=body)
    draw.text((panel[0]+18, panel[1]+45),
              f"孔口標高 {hole['collarElevationM']:.2f} m（精度未検証）",
              fill="#a12424", font=small)
    log_x0, log_x1 = panel[0]+25, panel[0]+150
    log_top, log_bottom = panel[1]+90, panel[3]-45
    total = hole["totalDepthM"]
    palette = {"VolcanicAshSoil":"#d9c49a", "FineGrainedSoil":"#bcae91",
               "CoarseGrainedSoil":"#e2c06d", "CoarseGrainedSoilWithFines":"#c99f68",
               "VolcanicRock":"#7c7781"}
    for item in hole["intervals"]:
        y0 = log_top+(log_bottom-log_top)*item["topDepthM"]/total
        y1 = log_top+(log_bottom-log_top)*item["bottomDepthM"]/total
        draw.rectangle((log_x0, y0, log_x1, y1),
                       fill=palette.get(item.get("broadMaterialClass"), "#cccccc"),
                       outline="#2c3338")
        if y1-y0 >= 17:
            draw.text((log_x1+10, y0),
                      f"{item['topDepthM']:g}–{item['bottomDepthM']:g} m  {item['sourceLabel']}",
                      fill="#222", font=small)
    draw.text((panel[0]+18, panel[3]-30), "原記載を保持・全区間 Unverified",
              fill="#a12424", font=small)
    target = Path(image_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    report = {"schemaVersion":"RegionalBoreholeContextRender-1.0",
              "renderBoundary":"RegionalContextDisplayOnly_NoSectionContacts",
              "sourceIds":[item[1]["sourceId"] for item in selected],
              "regionalContextBoreholeCount":len(selected),
              "columnIntervalCount":sum(len(item[1]["intervals"]) for item in selected),
              "drawnSectionContactCount":0,
              "absoluteElevationUsedForSectionGeometry":False,
              "imagePath":str(target.resolve())}
    report_path = target.with_suffix(".json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",
                           encoding="utf-8")
    return report
