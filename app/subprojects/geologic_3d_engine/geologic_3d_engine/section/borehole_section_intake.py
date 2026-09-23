"""Prepare borehole evidence for a section without silently correlating units."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from .borehole_evidence import project_boreholes_to_geographic_route
from .route_binding import build_route_binding


def load_and_project_borehole_file(path, route, maximum_offset_m):
    source = Path(path)
    raw = source.read_bytes()
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("ボーリングJSONをUTF-8として読み取れません。") from exc
    records = document.get("boreholes") if isinstance(document, Mapping) else None
    if not isinstance(records, list) or not records:
        raise ValueError("boreholes配列を1件以上含むJSONが必要です。")
    projected = project_boreholes_to_geographic_route(records, route, maximum_offset_m)
    accepted = [row for row in projected if row["projectionState"] == "Projected"]
    datums=sorted({row["verticalDatum"] for row in accepted})
    return {
        "schemaVersion":"BoreholeSectionIntake-1.0",
        "sourceFile":source.name,
        "sourceFileSha256":hashlib.sha256(raw).hexdigest(),
        "routeBinding":build_route_binding(route),
        "maximumProjectionOffsetM":float(maximum_offset_m),
        "boreholeCount":len(projected),
        "projectedCount":len(accepted),
        "rejectedByOffsetCount":len(projected)-len(accepted),
        "acceptedVerticalDatums":datums,
        "verticalDatumCompatibility":"Compatible" if len(datums)<=1 else "Mixed_NotComparable",
        "boreholes":projected,
        "correlationState":"NotCorrelated",
        "geometryAuthorization":"StickLogsAndObservedBoundariesOnly",
        "subsurfaceSurfaceAuthorization":False,
        "requiredNextEvidence":"Explicit reviewed stratigraphic correlation",
    }


def validate_projection_offset(value):
    if isinstance(value,bool):
        raise ValueError("ボーリング最大離隔は数値で入力してください。")
    try:
        result=float(value)
    except (TypeError,ValueError):
        raise ValueError("ボーリング最大離隔は数値で入力してください。")
    if not math.isfinite(result) or result < 0 or result > 10000:
        raise ValueError("ボーリング最大離隔は0～10000 mにしてください。")
    return result
