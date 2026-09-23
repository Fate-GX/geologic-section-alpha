"""GUI backend for fail-closed borehole route-role classification."""
from __future__ import annotations
import json
from pathlib import Path

from .section.borehole_route_role import classify_borehole_route_roles


def execute_borehole_route_role(source_path, route_conditions, constraint_offset_m,
                                context_offset_m, output_parent):
    source = Path(source_path).resolve()
    document = json.loads(source.read_text(encoding="utf-8"))
    holes = document.get("boreholes") if isinstance(document, dict) else None
    if not isinstance(holes, list) or not holes:
        raise ValueError("ボーリングコレクションにboreholes配列が必要です。")
    result = classify_borehole_route_roles(holes, route_conditions.vertices,
                                           constraint_offset_m, context_offset_m)
    output = Path(output_parent).resolve()/"borehole_route_roles"
    output.mkdir(parents=True, exist_ok=True)
    target = output/"borehole_route_roles.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    temporary.replace(target)
    return result, target
