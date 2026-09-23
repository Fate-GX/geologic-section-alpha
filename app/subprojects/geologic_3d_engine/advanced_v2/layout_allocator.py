"""Paper-space allocation policy for Advanced V2 publication layouts."""
from __future__ import annotations

import math


POLICY_ID = "ADV2-PAPERSPACE-BALANCED-DRAWABLE-RECT-1.0"
MAX_IMBALANCE_RATIO = 0.005


def allocate_a3_landscape_layout(*, legend_count: int,
                                 auxiliary_legend_count: int = 0,
                                 endpoint_line_count: int = 0) -> dict:
    """Allocate the viewport inside the sheet area left after mandatory blocks.

    Coordinates are paper-space millimetres.  The allocation is intentionally
    independent of model coordinates and language-specific label content.
    """
    if isinstance(legend_count, bool) or not isinstance(legend_count, int) or legend_count < 1:
        raise ValueError("positive integer legend count is required")
    if isinstance(auxiliary_legend_count, bool) or not isinstance(auxiliary_legend_count, int) or auxiliary_legend_count < 0:
        raise ValueError("non-negative integer auxiliary legend count is required")
    if isinstance(endpoint_line_count,bool) or not isinstance(endpoint_line_count,int) or not 0<=endpoint_line_count<=12:
        raise ValueError("endpoint annotation block exceeds supported sheet size")
    shift=4.0*endpoint_line_count+ (4.0 if endpoint_line_count else 0.0)
    sheet = {"left": 10.0, "right": 410.0, "bottom": 10.0, "top": 287.0}
    title_bottom = 268.0
    legend_rows = legend_count
    auxiliary_rows = 0 if auxiliary_legend_count == 0 else 1 + math.ceil(auxiliary_legend_count / 3)
    total_rows = legend_rows + auxiliary_rows
    # Geological explanations conventionally sit beside the section, not as a
    # floating band underneath it.  Reserve a right-hand explanation column.
    legend_top = 265.0-shift
    drawable = {"left": 17.0, "right": 313.0,
                "bottom": 36.0, "top": 265.0-shift}
    viewport = dict(drawable)
    width = drawable["right"] - drawable["left"]
    height = drawable["top"] - drawable["bottom"]
    horizontal = abs((viewport["left"] - drawable["left"]) -
                     (drawable["right"] - viewport["right"])) / width
    vertical = abs((viewport["bottom"] - drawable["bottom"]) -
                   (drawable["top"] - viewport["top"])) / height
    passed = horizontal <= MAX_IMBALANCE_RATIO and vertical <= MAX_IMBALANCE_RATIO
    return {"policyId": POLICY_ID, "paperUnits": "mm", "paperSize": "ISO_A3_Landscape",
            "sheetFrame": sheet, "titleBlockBottom": title_bottom,
            "legendBlockTop": legend_top, "legendBlockLeft": 320.0,
            "legendBlockRight": 403.0, "legendColumnCount": 1,
            "legendRowCount": legend_rows, "auxiliaryLegendRowCount": auxiliary_rows,
            "geologicalLegendCount": legend_count,
            "auxiliaryLegendCount": auxiliary_legend_count, "drawableRect": drawable,
            "viewportRect": viewport, "horizontalImbalanceRatio": horizontal,
            "verticalImbalanceRatio": vertical,
            "maximumImbalanceRatio": MAX_IMBALANCE_RATIO, "passed": passed}


def audit_layout_allocation(record: dict) -> dict:
    errors = []
    try:
        drawable = record["drawableRect"]
        viewport = record["viewportRect"]
        width = float(drawable["right"]) - float(drawable["left"])
        height = float(drawable["top"]) - float(drawable["bottom"])
        if width <= 0 or height <= 0:
            raise ValueError
        horizontal = abs((float(viewport["left"]) - float(drawable["left"])) -
                         (float(drawable["right"]) - float(viewport["right"]))) / width
        vertical = abs((float(viewport["bottom"]) - float(drawable["bottom"])) -
                       (float(drawable["top"]) - float(viewport["top"]))) / height
        if not all(math.isfinite(v) for v in (horizontal, vertical)):
            raise ValueError
        if horizontal > MAX_IMBALANCE_RATIO: errors.append("HorizontalLayoutImbalance")
        if vertical > MAX_IMBALANCE_RATIO: errors.append("VerticalLayoutImbalance")
        if float(viewport["left"]) < float(drawable["left"]) or \
           float(viewport["right"]) > float(drawable["right"]) or \
           float(viewport["bottom"]) < float(drawable["bottom"]) or \
           float(viewport["top"]) > float(drawable["top"]):
            errors.append("ViewportOutsideDrawableRect")
    except (KeyError, TypeError, ValueError):
        errors.append("InvalidLayoutAllocation")
        horizontal = vertical = None
    return {"passed": not errors, "errors": errors, "policyId": POLICY_ID,
            "horizontalImbalanceRatio": horizontal, "verticalImbalanceRatio": vertical}
