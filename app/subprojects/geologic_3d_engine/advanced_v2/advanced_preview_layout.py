from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw
from route_location import annotation_lines


CONTENT_LEFT = 130
CONTENT_RIGHT = 1710
LEGEND_TOP = 830
ROW_HEIGHT = 31
FOOTER_GAP = 18
BOTTOM_PADDING = 34


def _font(size):
    # Keep typography identical to the frozen renderer without changing it.
    from geologic_3d_engine.section.arbitrary_route_basic_section import _font as shared_font
    return shared_font(size)


def _visible_lithologies(model):
    bodies = model["syntheticEventArchitecture"]["renderBodies"]
    basement_id = model["composition"]["layersTopDown"][-1]["unitId"]
    visible_ids = {
        body["unitId"] for body in bodies
        if body["unitId"] == basement_id or any(body.get("activeMask", []))
    }
    return [item for item in model["renderingLithologies"] if item["unitId"] in visible_ids]


def _mapped_surface_legend(model):
    result = []
    for item in model.get("mappedSurfaceAtStations", []):
        key = (item.get("symbol"), item.get("lithologyJa"),
               item.get("formationAgeJa"), item.get("color"))
        if key not in result:
            result.append(key)
    return result[:4]


def _draw_checked(draw, xy, text, *, font, fill, anchor=None, boxes=None, role="text"):
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)
    box = draw.textbbox(xy, text, font=font, anchor=anchor)
    boxes.append({"role": role, "boxPx": list(box), "text": text})


def finalize_advanced_preview_layout(model, path):
    """Replace the frozen renderer footer with an Advanced-V2 dynamic footer.

    Geological geometry remains pixel-identical.  Only the presentation area
    below the section is rebuilt, with its height derived from visible content.
    """
    path = Path(path)
    original = Image.open(path).convert("RGB")
    visible = _visible_lithologies(model)
    surface = _mapped_surface_legend(model)
    lithology_rows = max(1, math.ceil(len(visible) / 2))
    surface_top = LEGEND_TOP + lithology_rows * ROW_HEIGHT + FOOTER_GAP
    footer_bottom = max(surface_top + 45 + len(surface) * 27,
                        surface_top + 100) + BOTTOM_PADDING
    endpoint_lines=annotation_lines(model.get("routeLocation",{}))
    if endpoint_lines:footer_bottom+=28+22*len(endpoint_lines)
    height = max(original.height, footer_bottom)
    image = Image.new("RGB", (original.width, height), "#f4f6f8")
    image.paste(original.crop((0, 0, original.width, LEGEND_TOP - 12)), (0, 0))
    draw = ImageDraw.Draw(image)
    boxes = []

    for index, item in enumerate(visible):
        column, row = index % 2, index // 2
        x = CONTENT_LEFT + column * 800
        y = LEGEND_TOP + row * ROW_HEIGHT
        draw.rectangle((x, y, x + 24, y + 20), fill=item["color"], outline="#555")
        _draw_checked(draw, (x + 34, y - 4), item["label"], font=_font(17),
                      fill="#263441", boxes=boxes, role="lithologyLegend")

    vertical_exaggeration = model.get("renderAudit", {}).get("verticalExaggeration", 1.0)
    _draw_checked(draw, (CONTENT_RIGHT, surface_top - 2),
                  f"水平・鉛直単位: m ／ 垂直誇張 約{vertical_exaggeration:.2f}倍",
                  font=_font(16), fill="#52606c", anchor="ra", boxes=boxes,
                  role="scaleDisclosure")
    _draw_checked(draw, (CONTENT_LEFT, surface_top), "GSJ地表地質（地表線だけに表示）",
                  font=_font(18), fill="#8a3b12", boxes=boxes, role="surfaceHeading")
    for index, (symbol, lithology, age, color) in enumerate(surface):
        x, y = CONTENT_LEFT, surface_top + 27 + index * 27
        draw.line((x, y + 9, x + 25, y + 9), fill=color or "#d4d4d4", width=5)
        label = f"{symbol or '未区分'}：{lithology or '地質図範囲外'} ({age or '年代未取得'})"
        if len(label) > 92:
            label = label[:91] + "…"
        _draw_checked(draw, (x + 34, y - 3), label, font=_font(15), fill="#263441",
                      boxes=boxes, role="surfaceLegend")

    attribution = model.get("renderAudit", {}).get("sourceAttributionText", "")
    attribution_y = surface_top + 34 + len(surface) * 27
    _draw_checked(draw, (CONTENT_LEFT, attribution_y), attribution, font=_font(14),
                  fill="#465663", boxes=boxes, role="sourceAttribution")
    for index,line in enumerate(endpoint_lines):
        _draw_checked(draw,(CONTENT_LEFT,attribution_y+28+index*22),line,font=_font(15),
                      fill="#263441",boxes=boxes,role="routeEndpoint")

    errors = []
    for item in boxes:
        left, top, right, bottom = item["boxPx"]
        if left < 0 or top < 0 or right > image.width or bottom > image.height:
            errors.append({"code": "PreviewTextOutsideCanvas", "role": item["role"],
                           "boxPx": item["boxPx"]})
    audit = {"schemaVersion": "AdvancedPreviewLayoutAudit-1.0",
             "passed": not errors, "canvasPx": [image.width, image.height],
             "visibleLithologyCount": len(visible),
             "mappedSurfaceLegendCount": len(surface), "textBoxes": boxes,
             "errors": errors}
    if errors:
        raise ValueError(f"advanced preview layout rejected: {errors}")
    image.save(path)
    return audit
