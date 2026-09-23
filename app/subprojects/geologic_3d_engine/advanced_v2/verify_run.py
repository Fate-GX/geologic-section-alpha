"""Independent fail-closed verification for an Advanced V2 run directory."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from layout_allocator import audit_layout_allocation
import sys

from frozen_guard import verify_frozen_basic_v1

EARTH_RADIUS_M = 6378137.0
REQUIRED_VISUAL_LAYOUTS = ("GEO_JP", "GEO_EN", "GEO_TOPOLOGY_QA", "GEO_MONOCHROME_QA")
COMMON_VISUAL_CHECKS = (
    "modelGeometryVisible", "geometryWithinViewport", "noBlankGeology",
    "noMojibake", "textWithinSheet", "requiredTicksVisible",
    "modelLowerLimitFilled", "contactLinesInForeground",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _visual_adjudication_errors(adjudication: dict | None, dwg: Path | None) -> list[str]:
    """Fail closed unless every publication layout was actually inspected."""
    if adjudication is None:
        return ["PostGenerationVisualReviewMissing"]
    errors = []
    if adjudication.get("schemaVersion") != "AdvancedV2PostGenerationVisualAdjudication-1.0":
        errors.append("VisualAdjudicationSchemaInvalid")
    if adjudication.get("decision") != "Accepted":
        errors.append("PostGenerationVisualReviewRejected" if adjudication.get("decision") == "Rejected"
                      else "PostGenerationVisualReviewIncomplete")
    if dwg is None or adjudication.get("reviewedDwgSha256") != _sha256(dwg):
        errors.append("VisualAdjudicationDwgBindingInvalid")
    if adjudication.get("plotOutputReviewed") is not True:
        errors.append("PlotOutputVisualReviewMissing")
    layouts = adjudication.get("layouts")
    if not isinstance(layouts, dict) or set(layouts) != set(REQUIRED_VISUAL_LAYOUTS):
        errors.append("VisualLayoutCoverageIncomplete")
        return errors
    for name in REQUIRED_VISUAL_LAYOUTS:
        checks = layouts.get(name)
        if not isinstance(checks, dict) or any(checks.get(key) is not True for key in COMMON_VISUAL_CHECKS):
            errors.append(f"VisualLayoutCheckFailed:{name}")
        if name == "GEO_MONOCHROME_QA" and (not isinstance(checks, dict) or checks.get("monochromeEffective") is not True):
            errors.append("MonochromeVisualCheckFailed")
        if name == "GEO_TOPOLOGY_QA" and (not isinstance(checks, dict) or checks.get("hatchesHidden") is not True):
            errors.append("TopologyVisualCheckFailed")
    return errors


def _reopen_report_errors(report_text: str) -> list[str]:
    errors = []
    if "ADVANCED_V2_REOPEN_VALIDATION=OK" not in report_text:
        errors.append("DwgReopenValidationFailed")
    if "LAYOUTS_OK=true" not in report_text:
        errors.append("DwgLayoutStructuralValidationMissing")
    if "BASAL_CONTINUATION_HATCHES=1" not in report_text:
        errors.append("DwgBasalContinuationValidationMissing")
    viewport_line = next((line for line in report_text.splitlines() if line.startswith("VIEWPORTS=")), "")
    for name in REQUIRED_VISUAL_LAYOUTS:
        entry = next((part for part in viewport_line.removeprefix("VIEWPORTS=").split("|")
                      if part.startswith(name + ":")), "")
        # AutoCAD persists On=False/Number=-1 for non-current paper layouts.
        # Saved camera/aperture/lock state is the structural invariant; actual
        # visibility is proved separately by the hash-bound plot review.
        # Height is allocated dynamically from the evidence-bounded legend row
        # count (for the current matrix it is 184 mm, older fixtures used 204).
        # The native validator already compares the saved rectangle with the
        # contract; here require its invariant width and a reported positive
        # rectangular aperture without freezing one historical height.
        size = entry.split("SIZE=(", 1)[1].split(")", 1)[0] if "SIZE=(" in entry else ""
        try:
            viewport_width, viewport_height = (float(value) for value in size.split(","))
            valid_size = abs(viewport_width - 386.0) <= 1e-6 and viewport_height > 0.0
        except (TypeError, ValueError):
            valid_size = False
        if (not entry or "LOCKED=True" not in entry or "VC=(" not in entry or
                "VH=" not in entry or not valid_size):
            errors.append(f"DwgViewportValidationMissing:{name}")
    return errors


def _distance_m(route) -> float:
    (lon1, lat1), (lon2, lat2) = route
    lon1, lat1, lon2, lat2 = map(math.radians, (lon1, lat1, lon2, lat2))
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return EARTH_RADIUS_M * 2 * math.asin(min(1.0, math.sqrt(value)))


def verify_advanced_run(project_root, run_directory) -> dict:
    root = Path(project_root).resolve()
    run_dir = Path(run_directory).resolve()
    engine = root / "subprojects/geologic_3d_engine"
    if str(engine) not in sys.path:
        sys.path.insert(0, str(engine))
    from geologic_3d_engine.export.contract_integrity import canonical_json_bytes, verify_integrity_envelope

    errors = []
    adjudication_path = run_dir / "post_generation_visual_adjudication.json"
    adjudication = None
    if adjudication_path.is_file():
        try:
            adjudication = json.loads(adjudication_path.read_text(encoding="utf-8"))
            if adjudication.get("decision") == "Rejected":
                errors.append("PostGenerationVisualReviewRejected")
        except (OSError, ValueError):
            errors.append("VisualAdjudicationInvalid")
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        refusal_path = run_dir / "typed_refusal.json"
        if not refusal_path.is_file():
            return {"passed": False, "errors": ["RunManifestMissing"]}
        refusal = json.loads(refusal_path.read_text(encoding="utf-8"))
        refusal_errors = []
        allowed = {"PlanEvidenceAcquisitionFailed", "SurroundingEvidenceAcquisitionFailed",
                   "UnderlyingNaturalDomainUnavailable", "UnsupportedOrAmbiguousGeologicalDomain"}
        allowed.add("AdvancedContactGeometryRejected")
        if refusal.get("schemaVersion") != "AdvancedJapanSectionRefusal-2.0":
            refusal_errors.append("UnexpectedRefusalSchema")
        if refusal.get("passed") is not False or refusal.get("dwgCreated") is not False or \
                refusal.get("fabricatedFallbackUsed") is not False:
            refusal_errors.append("UnsafeRefusalState")
        if refusal.get("reason") not in allowed: refusal_errors.append("UnknownRefusalReason")
        if list(run_dir.rglob("*.dwg")): refusal_errors.append("DwgPresentAfterRefusal")
        try:
            req = refusal["request"]
            if abs(_distance_m(req["routeLonLat"]) - float(req["length_m"])) > 1e-5:
                refusal_errors.append("RouteLengthMismatch")
        except (KeyError, TypeError, ValueError):
            refusal_errors.append("InvalidRouteRecord")
        frozen = verify_frozen_basic_v1(root)
        if not frozen["passed"]: refusal_errors.append("FrozenBasicV1Changed")
        return {"schemaVersion":"AdvancedJapanSectionVerification-2.0",
                "passed":not refusal_errors, "outcome":"TypedRefusal",
                "refusalReason":refusal.get("reason"), "errors":refusal_errors,
                "frozenBasicV1":frozen, "localGeologicalTruthEstablished":False}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema = manifest.get("schemaVersion")
    if schema not in {"AdvancedJapanSectionRun-2.0", "AdvancedJapanSectionRun-2.1"}:
        errors.append("UnexpectedManifestSchema")
    if schema == "AdvancedJapanSectionRun-2.1":
        reuse = manifest.get("sourceReuseBoundary", [])
        source_ids = {row.get("sourceId") for row in reuse if isinstance(row, dict)}
        if source_ids != {"GSI-ELEVATION-TILE", "GSJ-SEAMLESS-V2-API"} or \
                any(not row.get("termsUrl") or not row.get("authority") for row in reuse):
            errors.append("SourceReuseBoundaryIncomplete")
    if manifest.get("decision") != "Experimental" or manifest.get("realRegionAuthorized") is not False:
        errors.append("UnsafeAuthorizationClaim")
    frozen = verify_frozen_basic_v1(root)
    if not frozen["passed"]: errors.append("FrozenBasicV1Changed")

    resolved = []
    for row in manifest.get("artifacts", []):
        portable = row.get("projectRelativePath")
        path = ((root / portable).resolve() if isinstance(portable, str) and portable else
                Path(row.get("path", "")).resolve())
        if not path.is_file():
            errors.append(f"ArtifactMissing:{path.name}")
        elif _sha256(path) != row.get("sha256"):
            errors.append(f"ArtifactHashMismatch:{path.name}")
        else:
            resolved.append(path)

    request = manifest.get("request", {})
    try:
        actual = _distance_m(request["routeLonLat"])
        if abs(actual - float(request["length_m"])) > 1e-5: errors.append("RouteLengthMismatch")
    except (KeyError, TypeError, ValueError):
        errors.append("InvalidRouteRecord")

    contracts = [p for p in resolved if p.name == "native_dwg_contract_envelope.json"]
    if len(contracts) != 1:
        errors.append("DwgContractArtifactCountMismatch")
        contract = None
    else:
        try:
            document = json.loads(contracts[0].read_text(encoding="utf-8"))
            contract, validation = verify_integrity_envelope(document["geologicContractEnvelope"])
            unsigned = {k: v for k, v in contract.items() if k not in {"contractSha256", "validation"}}
            if hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest() != contract.get("contractSha256"):
                errors.append("InnerContractDigestMismatch")
            if not validation.get("passed"): errors.append("DwgContractValidationFailed")
        except Exception:
            contract = None
            errors.append("DwgContractEnvelopeInvalid")

    reports = [p for p in resolved if p.name.endswith("_reopen_validation.txt")]
    dwgs = [p for p in resolved if p.suffix.lower() == ".dwg"]
    models = [p for p in resolved if p.name == "model.json"]
    if len(models) != 1:
        errors.append("ModelArtifactCountMismatch")
    else:
        try:
            model = json.loads(models[0].read_text(encoding="utf-8"))
            selection = model["lithologySelection"]
            if (selection.get("passed") is not True or
                    selection.get("mappedSurfaceEvidenceUsedAsVerticalSequence") is not False or
                    selection.get("observedCount") != 0 or
                    selection.get("literatureCount") != 0 or
                    selection.get("candidateLithologyCount", selection.get("selectedCount", 0)) < 6 or
                    selection.get("selectedCount", 0) < 4):
                errors.append("LithologySelectionBoundaryInvalid")
            if model.get("contactRangeEnsembleAudit", {}).get("passed") is not True:
                errors.append("ContactRangeEnsembleAuditMissing")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            errors.append("ModelAuditRecordInvalid")
    if manifest.get("primaryArtifact") == "NativeDwg":
        if len(dwgs) != 1 or dwgs[0].read_bytes()[:6] != b"AC1032": errors.append("NativeDwgInvalid")
        if len(reports) != 1:
            errors.append("DwgReopenValidationMissing")
        else:
            errors.extend(_reopen_report_errors(reports[0].read_text(encoding="utf-8")))
        errors.extend(_visual_adjudication_errors(adjudication, dwgs[0] if len(dwgs)==1 else None))
    if contract is not None:
        geological_polygons = [row for row in contract.get("polygons", [])
                               if row.get("materialClassification") != "SyntheticBasalContinuation"]
        expected = 0 if request.get("contact_lines") == "Hide" else len(geological_polygons)
        if len(contract.get("contactLines", [])) != expected: errors.append("ContactDisplayPolicyMismatch")
        if not contract.get("terrainLine", {}).get("vertices"): errors.append("TerrainLineMissing")
        drafting = contract.get("drafting", {})
        if not drafting.get("elevationTicksM") or drafting.get("bilateralElevationTicks") is not True:
            errors.append("ElevationDraftingIncomplete")
        try:
            vertices = [v for polygon in contract["polygons"] for v in polygon["vertices"]]
            xs = [float(v[0]) for v in vertices]
            ys = [float(v[1]) for v in vertices]
            x_ticks = [float(v) for v in drafting["horizontalTicksM"]]
            y_ticks = [float(v) for v in drafting["elevationTicksM"]]
            tolerance = 1e-7
            if min(x_ticks) > min(xs) + tolerance or max(x_ticks) < max(xs) - tolerance:
                errors.append("HorizontalScaleDoesNotEncloseGeometry")
            if min(y_ticks) > min(ys) + tolerance or max(y_ticks) < max(ys) - tolerance:
                errors.append("VerticalScaleDoesNotEncloseGeometry")
            lower_boundary = [float(v) for v in drafting["modelLowerBoundaryElevationM"]]
            frame_lower = float(drafting["drawingFrameLowerM"])
            if drafting.get("modelLowerLimitClass") != "VariableSyntheticModelBoundary" or \
               drafting.get("belowModelLimitStatus") != "SyntheticBasalContinuation":
                errors.append("ModelLowerLimitSemanticsMissing")
            continuation = [row for row in contract["polygons"]
                            if row.get("materialClassification") == "SyntheticBasalContinuation"]
            if len(lower_boundary) != len(contract["terrainLine"]["vertices"]):
                errors.append("ModelLowerBoundaryShapeInvalid")
            if abs(min(y_ticks) - frame_lower) > tolerance or len(continuation) != 1:
                errors.append("BasalContinuationFrameGapInvalid")
            elif abs(min(float(v[1]) for v in continuation[0]["vertices"]) - frame_lower) > tolerance:
                errors.append("BasalContinuationFrameGapInvalid")
            elif (continuation[0].get("legendGroup") != "Geology" or
                  continuation[0].get("displayCategory") != "GeologicalPriorContinuation" or
                  continuation[0].get("basisType") != "SyntheticAssumption" or
                  continuation[0].get("continuationOfUnitId") != continuation[0].get("unitId") or
                  continuation[0].get("hatchPattern") != "SOLID"):
                errors.append("BasalContinuationClassificationInvalid")
            if any(not row.get("hatchLayer", "").startswith("30_岩相カラー_") or
                   row.get("displayName", "").replace(" ", "_") not in row.get("hatchLayer", "")
                   for row in contract["polygons"]):
                errors.append("LithologyLayerSuffixMissing")
            if not audit_layout_allocation(drafting.get("layoutAllocation", {}))["passed"]:
                errors.append("PaperSpaceAllocationInvalid")
            if validation.get("modelLowerBoundaryMatchesDisplayBase") is not True or \
               validation.get("basalContinuationCoversDrawingFrameGap") is not True or \
               validation.get("basalContinuationPolygonCount") != 1 or \
               validation.get("basalContinuationUsesExistingDeepestLithology") is not True or \
               validation.get("paperSpaceAllocationPassed") is not True:
                errors.append("ModelLowerLimitValidationMissing")
        except (KeyError, TypeError, ValueError):
            errors.append("DrawingExtentAuditInvalid")

    return {"schemaVersion": "AdvancedJapanSectionVerification-2.0", "passed": not errors,
            "errors": errors, "artifactCount": len(resolved), "frozenBasicV1": frozen,
            "localGeologicalTruthEstablished": False}
