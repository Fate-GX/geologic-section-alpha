"""Advanced-only DWG options layered over the frozen v1 export contract."""
from __future__ import annotations
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path
from layout_allocator import allocate_a3_landscape_layout, audit_layout_allocation
from current_lithology_terminology import require_current_publication_terminology
from regional_bedrock import audit_regional_bedrock


MAXIMUM_UNIT_AREA_FRACTION = {
    "UnconsolidatedSedimentTerrain": 0.45,
    "SedimentaryRockTerrain": 0.45,
    "VolcanicTerrain": 0.45,
    # Massive crystalline/tectonic domains may legitimately be dominated by
    # one mapped rock mass; keep a looser display-prior gate there.
    "PlutonicTerrain": 0.72,
    "AccretionaryComplex": 0.68,
    "MetamorphicBelt": 0.68,
}


class AdvancedDwgContractError(ValueError):
    """Fail-closed contract error carrying every known portrayal finding."""

    def __init__(self, message: str, findings: list[dict]):
        super().__init__(message)
        self.findings = findings


def _polygon_area(vertices) -> float:
    points = [(float(row[0]), float(row[1])) for row in vertices]
    if len(points) < 3:
        return 0.0
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2)
                   in zip(points, points[1:] + points[:1]))) * 0.5


def _audit_unit_area_balance(contract: dict, domain: str,
                             verified_basal_continuation_ids=frozenset(),
                             include_synthetic_basal_continuation: bool = False) -> dict:
    """Audit portrayed geological units without conflating drafting continuation.

    The polygon below the calculated model limit exists only to close the rounded
    drawing frame.  It remains measurable, but is excluded from the authoritative
    model-interval balance unless explicitly requested for a diagnostic summary.
    """
    areas = {}
    excluded_area = 0.0
    for polygon in contract.get("polygons", []):
        if polygon.get("legendGroup") != "Geology":
            continue
        area = _polygon_area(polygon.get("vertices", []))
        if (polygon.get("polygonId") in verified_basal_continuation_ids
                and not include_synthetic_basal_continuation):
            excluded_area += area
            continue
        unit_id = polygon.get("unitId")
        areas[unit_id] = areas.get(unit_id, 0.0) + area
    total = sum(areas.values())
    fractions = {key: value / total for key, value in areas.items()} if total > 0 else {}
    limit = MAXIMUM_UNIT_AREA_FRACTION.get(domain, 0.68)
    largest_id, largest = max(fractions.items(), key=lambda row: row[1], default=(None, 0.0))
    passed = total > 0 and largest <= limit + 1e-12
    return {"passed": passed, "domain": domain,
            "auditScope": ("DrawingFrameIncludingSyntheticBasalContinuation"
                           if include_synthetic_basal_continuation else
                           "CalculatedGeologicalModelInterval"),
            "syntheticBasalContinuationExcluded": not include_synthetic_basal_continuation,
            "excludedSyntheticBasalContinuationArea": excluded_area,
            "maximumAllowedFraction": limit,
            "largestUnitId": largest_id, "largestUnitAreaFraction": largest,
            "unitAreaFractions": fractions,
            "errors": [] if passed else ["SingleLithologyAreaDominanceExceeded"]}


def _verified_basal_continuation_ids(contract: dict, model: dict,
                                     frame_lower: float) -> frozenset[str]:
    """Return geometry-bound continuation IDs or fail closed.

    A caller-controlled classification label is not authority.  The sole
    continuation must bind the declared display base, the complete calculated
    lower boundary, and the rounded drawing-frame bottom in canonical order.
    """
    rows = [row for row in contract.get("polygons", [])
            if row.get("materialClassification") == "SyntheticBasalContinuation"]
    if len(rows) != 1:
        raise ValueError("exactly one synthetic basal continuation is required")
    row = rows[0]
    domain = model.get("modelDomain", {})
    base_id = domain.get("displayBaseUnitId")
    stations = [float(value) for value in model.get("stationsM", [])]
    lower = [float(value) for value in domain.get("lowerBoundaryElevationM", [])]
    expected = ([[x, y] for x, y in zip(stations, lower)] +
                [[x, float(frame_lower)] for x in reversed(stations)])
    if (row.get("polygonId") != "ADV2-BASAL-CONTINUATION-0" or
            row.get("unitId") != base_id or
            row.get("continuationOfUnitId") != base_id or
            row.get("basisType") != "SyntheticAssumption" or
            row.get("displayCategory") != "GeologicalPriorContinuation" or
            row.get("vertices") != expected):
        raise ValueError("synthetic basal continuation geometry binding rejected")
    return frozenset({row["polygonId"]})


def _lithology_hatch_layer(index: int, label: str) -> str:
    """Return a native-DWG layer name that identifies the represented lithology."""
    suffix = unicodedata.normalize("NFC", str(label)).strip()
    suffix = re.sub(r'[<>/\\\";:?*|,=／＼：；？＊｜，＝＜＞]+', "_", suffix)
    suffix = re.sub(r"\s+", "_", suffix).strip("_.") or "岩相未命名"
    suffix = re.sub(r"_+", "_", suffix)
    return f"30_岩相カラー_{index:02d}_{suffix[:48]}"


def _pinchout_closure_runs(mask):
    """Return active runs extended to their adjacent zero-thickness nodes."""
    values = [bool(value) for value in mask]
    start = None
    for index, active in enumerate(values + [False]):
        if active and start is None:
            start = index
        elif not active and start is not None:
            stop = index
            yield max(0, start - 1), min(len(values), stop + 1)
            start = None


def _close_advanced_pinchouts(contract: dict, model: dict) -> None:
    """Close Advanced V2 pinch-outs at their zero-thickness apex nodes."""
    stations = [float(value) for value in model["stationsM"]]
    bodies = model["syntheticEventArchitecture"]["renderBodies"]
    styles = {row["unitId"]: row for row in model["renderingLithologies"]}
    affected = {row["unitId"] for row in bodies if row.get("allowPinchout")}
    if not affected:
        return
    contract["polygons"] = [row for row in contract["polygons"] if row.get("unitId") not in affected]
    contract["contactLines"] = [row for row in contract["contactLines"] if row.get("unitId") not in affected]
    for body_index, body in enumerate(bodies):
        if body.get("unitId") not in affected:
            continue
        top = [float(value) for value in body["topElevationM"]]
        bottom = [float(value) for value in body["bottomElevationM"]]
        mask = [bool(flag) and upper > lower + 1e-9
                for flag, upper, lower in zip(body["activeMask"], top, bottom)]
        style = styles[body["unitId"]]
        rgb = [int(style["color"][offset:offset + 2], 16) for offset in (1, 3, 5)]
        for run_index, (start, stop) in enumerate(_pinchout_closure_runs(mask)):
            forward = [[stations[i], top[i]] for i in range(start, stop)]
            reverse = [[stations[i], bottom[i]] for i in range(stop - 1, start - 1, -1)]
            if len(forward) < 2:
                continue
            contract["polygons"].append({
                "polygonId": f"{body['unitId']}-ADV2-{run_index}", "unitId": body["unitId"],
                "displayName": style["label"], "boundaryLayer": "19_ハッチ境界_非印刷",
                "hatchLayer": _lithology_hatch_layer(body_index + 1, style["label"]),
                "trueColorRGB": rgb, "vertices": forward + reverse,
                "closed": True, "hatchPattern": "SOLID", "associative": True,
                "legendGroup": "Geology", "displayCategory": "GeologicalInterpretation",
                "sourceCoordinateFrame": "RouteStationM_ElevationM",
            })
            contract["contactLines"].append({
                "contactId": f"CONTACT-{body['unitId']}-ADV2-{run_index}",
                "unitId": body["unitId"], "layer": "20_岩相区分線_推定",
                "vertices": forward, "lineType": "Continuous", "drawOrder": "Foremost",
            })


def _enclosing_ticks(lower: float, upper: float, spacing: float) -> list[float]:
    """Return scale ticks whose first/last values enclose the plotted geometry."""
    if not all(math.isfinite(value) for value in (lower, upper, spacing)):
        raise ValueError("drawing extents and tick spacing must be finite")
    if spacing <= 0 or upper < lower:
        raise ValueError("tick spacing must be positive and extents must be ordered")
    # Route projection and accumulated station distances can place an intended
    # tick endpoint a few ULPs on either side of its exact decimal value.  Snap
    # only within a sub-micrometre, spacing-relative numerical tolerance; real
    # geometric overrun remains enclosed by an additional tick.
    tolerance = max(1e-9, abs(spacing) * 1e-9)
    def snapped(value: float) -> float:
        nearest = round(value / spacing) * spacing
        return nearest if abs(value - nearest) <= tolerance else value
    start = math.floor(snapped(lower) / spacing) * spacing
    stop = math.ceil(snapped(upper) / spacing) * spacing
    count = int(round((stop - start) / spacing))
    return [start + index * spacing for index in range(count + 1)]


def _endpoint_priority_ticks(ticks, length, spacing):
    """Keep exact A/B values; omit a regular label too close to B.

    Reserve half a regular interval for the endpoint label. This only selects
    annotation values: native axes, geology and the actual endpoint stay exact.
    AutoCAD's persisted DBText.GeometricExtents collision gate remains mandatory.
    """
    if not all(math.isfinite(v) and v > 0 for v in (length, spacing)):
        raise ValueError("positive finite length and spacing are required")
    return [x for x in ticks if x == 0 or (0 < x <= length-spacing/2)] + [length]


def write_advanced_dwg_handoff(model: dict, output_path) -> Path:
    bedrock_audit = audit_regional_bedrock(model)
    if not bedrock_audit["passed"]:
        raise ValueError("regional bedrock gate rejected: " + ",".join(bedrock_audit["errors"]))
    from geologic_3d_engine.export.arbitrary_route_dwg import build_arbitrary_route_dwg_contract
    from geologic_3d_engine.export.contract_integrity import build_integrity_envelope, canonical_json_bytes
    require_current_publication_terminology(model)
    contract = build_arbitrary_route_dwg_contract(model)
    _close_advanced_pinchouts(contract, model)
    english_labels = model.get("advancedEnglishUnitLabels", {})
    for polygon in contract["polygons"]:
        polygon["displayNameEn"] = english_labels.get(polygon["unitId"], polygon["unitId"])
        polygon.setdefault("legendGroup", "Geology")
        polygon.setdefault("displayCategory", "GeologicalInterpretation")
    unit_order = {row["unitId"]: index for index, row in
                  enumerate(model["syntheticEventArchitecture"]["renderBodies"], start=1)}
    styles = {row["unitId"]: row for row in model["renderingLithologies"]}
    for polygon in contract["polygons"]:
        if polygon.get("legendGroup") != "Geology":
            continue
        unit_id = polygon["unitId"]
        polygon["hatchLayer"] = _lithology_hatch_layer(
            unit_order[unit_id], styles[unit_id]["label"])
    domain = model.get("modelDomain", {})
    if domain.get("lowerLimitClass") != "VariableSyntheticModelBoundary" or \
       domain.get("belowLimitStatus") != "SyntheticBasalContinuationEligible" or \
       domain.get("lowerLimitIsGeologicalContact") is not False:
        raise ValueError("explicit synthetic basal-continuation semantics are required")
    lower_boundary = [float(value) for value in domain.get("lowerBoundaryElevationM", [])]
    if len(lower_boundary) != len(model.get("stationsM", [])) or not all(map(math.isfinite, lower_boundary)):
        raise ValueError("finite model lower-boundary array is required")
    display_base_id = domain.get("displayBaseUnitId")
    base_polygons = [row for row in contract["polygons"] if row.get("unitId") == display_base_id]
    if not base_polygons:
        raise ValueError("display base is missing")
    show = model.get("renderAudit", {}).get("contactLines", "Show") == "Show"
    if not show:
        contract["contactLines"] = []
    geological_vertices = [vertex for polygon in contract["polygons"] for vertex in polygon["vertices"]]
    drafting = contract["drafting"]
    specification = model["draftingSpecification"]
    drafting["horizontalTicksM"] = _enclosing_ticks(
        min(float(vertex[0]) for vertex in geological_vertices),
        max(float(vertex[0]) for vertex in geological_vertices),
        float(specification["horizontalTickM"]),
    )
    # Arbitrary A/B routes rarely end on a round tick. Keep the real endpoint,
    # never place the next rounded tick beyond the section's right-hand axis.
    length=float(drafting["actualSectionLengthM"])
    drafting["horizontalTicksM"] = _endpoint_priority_ticks(
        drafting["horizontalTicksM"], length, float(specification["horizontalTickM"]))
    drafting["elevationTicksM"] = _enclosing_ticks(
        min(float(vertex[1]) for vertex in geological_vertices),
        max(float(vertex[1]) for vertex in geological_vertices),
        float(specification["verticalTickM"]),
    )
    frame_lower = float(min(drafting["elevationTicksM"]))
    stations = [float(value) for value in model["stationsM"]]
    if any(value < frame_lower - 1e-8 for value in lower_boundary):
        raise ValueError("rounded drawing frame does not enclose the model boundary")
    continuation_vertices = ([[x, y] for x, y in zip(stations, lower_boundary)] +
                             [[x, frame_lower] for x in reversed(stations)])
    base_style = styles[display_base_id]
    base_rgb = [int(base_style["color"][offset:offset + 2], 16) for offset in (1, 3, 5)]
    base_layer = _lithology_hatch_layer(unit_order[display_base_id], base_style["label"])
    contract["polygons"].append({
        "polygonId": "ADV2-BASAL-CONTINUATION-0", "unitId": display_base_id,
        "displayName": base_style["label"],
        "displayNameEn": english_labels.get(display_base_id, display_base_id),
        "materialClassification": "SyntheticBasalContinuation",
        "geologicalInterpretation": True,
        "basisType": "SyntheticAssumption",
        "continuationOfUnitId": display_base_id,
        "continuationRuleId": "GEO-BASE-CONTINUATION-001",
        "boundaryLayer": "19_ハッチ境界_非印刷", "hatchLayer": base_layer,
        "trueColorRGB": base_rgb, "vertices": continuation_vertices, "closed": True,
        "hatchPattern": "SOLID", "displayHatchPattern": "SOLID",
        "associative": True,
        "legendGroup": "Geology", "displayCategory": "GeologicalPriorContinuation",
        "sourceCoordinateFrame": "RouteStationM_ElevationM",
    })
    domain_name = model.get("lithologySelection", {}).get("domain", "Unresolved")
    verified_continuation_ids = _verified_basal_continuation_ids(
        contract, model, frame_lower)
    area_balance = _audit_unit_area_balance(
        contract, domain_name, verified_continuation_ids)
    drawing_frame_area_balance = _audit_unit_area_balance(
        contract, domain_name, verified_continuation_ids,
        include_synthetic_basal_continuation=True)
    if not area_balance["passed"]:
        parallelism = model.get("modelAudit", {}).get("contactTerrainParallelismAudit", {})
        depth_gate = model.get("advancedContactGeometryAudit", {}).get(
            "plutonicDepthDependentParallelismAudit", {})
        findings = [{"gate": "UnitAreaBalance", "severity": "Error",
                     "passed": False, "details": area_balance}]
        if parallelism and not parallelism.get("passed", True):
            findings.append({"gate": "GenericTerrainParallelism", "severity": "Advisory",
                             "passed": False, "details": parallelism,
                             "note": "Generic translated-copy diagnostic; applicability is architecture-specific"})
        if depth_gate:
            findings.append({"gate": "PlutonicDepthDependentParallelism",
                             "severity": "Error" if not depth_gate.get("passed") else "Information",
                             "passed": bool(depth_gate.get("passed")), "details": depth_gate})
        raise AdvancedDwgContractError(
            "geological portrayal rejected: " + ",".join(area_balance["errors"]) +
            f" ({area_balance['largestUnitId']}={area_balance['largestUnitAreaFraction']:.3f})",
            findings)
    drafting["modelLowerBoundaryElevationM"] = lower_boundary
    drafting["minimumGeologicalElevationM"] = min(lower_boundary)
    drafting["drawingFrameLowerM"] = frame_lower
    drafting["modelLowerLimitClass"] = domain["lowerLimitClass"]
    drafting["belowModelLimitStatus"] = "SyntheticBasalContinuation"
    drafting["modelLowerLimitNoteJa"] = (
        f"図枠下端までの深部は最下位岩相「{base_style['label']}」の合成的下方延長"
        "（観測事実ではない）")
    drafting["modelLowerLimitNoteEn"] = (
        "Below the calculated model boundary: synthetic downward continuation of "
        f"the deepest displayed unit ({english_labels.get(display_base_id, display_base_id)}); not observed")
    geological_units = {row["unitId"] for row in contract["polygons"]
                         if row.get("legendGroup") == "Geology"}
    from route_location import annotation_lines
    route_location=model.get("routeLocation",{})
    selected_request=model.get("advancedExtension",{}).get("request",{})
    if selected_request.get("routeDefinition")=="OrderedEndpointsAB" and not route_location:
        raise ValueError("EndpointLocationRequired")
    endpoint_lines=annotation_lines(route_location)
    if endpoint_lines:
        drafting["sectionId"]="A-B"
        selected=model.get("advancedExtension",{}).get("request",{}).get("routeLonLat")
        records=route_location.get("endpoints",[])
        if ([r.get("endpoint") for r in records]!=["A","B"] or
            [[r.get("longitude"),r.get("latitude")] for r in records]!=selected or
            model.get("routeLonLat")!=selected):
            raise ValueError("EndpointLocationBindingMismatch")
        drafting["routeEndpointLocation"]=route_location
        drafting["endpointAnnotationLines"]=endpoint_lines
    drafting["layoutAllocation"] = allocate_a3_landscape_layout(
        legend_count=len(geological_units), auxiliary_legend_count=0,
        endpoint_line_count=len(endpoint_lines))
    layout_audit = audit_layout_allocation(drafting["layoutAllocation"])
    if not layout_audit["passed"]:
        raise ValueError(f"paper-space allocation rejected: {layout_audit['errors']}")
    # Layouts contain viewports only.  The complete sheet composition lives in
    # model space and is viewed through this full-sheet aperture.
    drafting["modelSpaceViewportRect"] = {"left": 10.0, "right": 410.0,
                                            "bottom": 10.0, "top": 287.0}
    contract["validation"]["drawingScaleEnclosesGeometry"] = True
    contract["validation"]["polygonCount"] = len(contract["polygons"])
    contract["validation"]["contactLineCount"] = len(contract["contactLines"])
    contract["validation"]["contactLineForemost"] = show
    contract["validation"]["modelLowerBoundaryMatchesDisplayBase"] = True
    contract["validation"]["basalContinuationCoversDrawingFrameGap"] = True
    contract["validation"]["basalContinuationPolygonCount"] = 1
    contract["validation"]["basalContinuationUsesExistingDeepestLithology"] = True
    contract["validation"]["basalContinuationBasisType"] = "SyntheticAssumption"
    contract["validation"]["unitAreaBalance"] = area_balance
    contract["validation"]["drawingFrameUnitAreaBalanceDiagnostic"] = drawing_frame_area_balance
    contract["validation"]["geologicalLegendUnitCount"] = len(geological_units)
    contract["validation"]["modelExtentLegendUnitCount"] = 0
    contract["validation"]["paperSpaceAllocationPassed"] = True
    contract["validation"]["paperSpaceMaximumImbalanceRatio"] = layout_audit["horizontalImbalanceRatio"]
    contract["validation"]["pinchoutClosurePolicy"] = "AdjacentZeroThicknessApex"
    unsigned = {key:value for key,value in contract.items() if key not in {"contractSha256", "validation"}}
    contract["contractSha256"] = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    envelope = build_integrity_envelope(contract, contract["validation"], "advanced-arbitrary-route-dwg-2.0")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"geologicContractEnvelope":envelope}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    return target
