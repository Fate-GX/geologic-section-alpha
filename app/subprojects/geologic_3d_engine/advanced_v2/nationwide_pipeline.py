from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from uuid import uuid4

from frozen_guard import verify_frozen_basic_v1
from route_request import AdvancedJapanSectionRequest
from domain_profiles import profile_for_domain, contextual_profile_for_domain, broad_profile_for_domain
from context_inference import infer_natural_domain, context_evidence_from_plan
from advanced_domain_classifier import classify_plan_advanced
from advanced_dwg_contract import write_advanced_dwg_handoff
from advanced_contact_geometry import (apply_advanced_contact_geometry,
                                        audit_advanced_contact_geometry,
                                        audit_contact_sampler_implementation)
from lithology_selector import select_evidence_bounded_lithologies
from facies_architecture import audit_facies_portrayal
from terrain_morphology import classify_terrain_morphology
from terrain_conditioning import condition_profile_for_terrain
from gsi_landform_evidence import acquire_landform_evidence
from synthetic_terrain_qa import audit_natural_terrain_texture
from advanced_preview_layout import finalize_advanced_preview_layout
from route_location import resolve_route_locations
from regional_lithology_data import write_and_load_regional_dataset
from regional_bedrock import (resolve_regional_bedrock, acquire_bedrock_neighborhood,
                              apply_regional_bedrock_geometry, audit_regional_bedrock)
from current_lithology_terminology import (normalize_model_added_lithologies,
                                           require_current_publication_terminology)

SUPPORTED_DOMAINS = {"VolcanicTerrain", "SedimentaryRockTerrain", "AccretionaryComplex",
                     "PlutonicTerrain", "MetamorphicBelt", "UnconsolidatedSedimentTerrain"}


def _engine_imports(project_root):
    engine = Path(project_root) / "subprojects/geologic_3d_engine"
    if str(engine) not in sys.path: sys.path.insert(0, str(engine))
    from geologic_3d_engine.section.arbitrary_route_basic_section import (
        build_arbitrary_route_basic_model, render_arbitrary_route_basic_section,
        audit_arbitrary_route_basic_model)
    from geologic_3d_engine.section.geological_domain_classifier import classify_plan_geological_domain
    from geologic_3d_engine.section.geological_domain_classifier import _domain_for_legend
    from advanced_native_dwg_runner import run_advanced_native_dwg
    from geologic_3d_engine.modeling.domain_model_library import select_domain_model
    return (build_arbitrary_route_basic_model, render_arbitrary_route_basic_section,
            audit_arbitrary_route_basic_model,
            classify_plan_geological_domain, run_advanced_native_dwg,
            select_domain_model, _domain_for_legend)


def _load_acquisition(project_root):
    path = Path(project_root) / "research/geologic_dwg_generation/tools/build_gsi_plan_section_demo.py"
    spec = importlib.util.spec_from_file_location("advanced_v2_gsi_plan", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.run


def _sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _artifact_record(root, path):
    resolved = Path(path).resolve()
    try:
        relative = resolved.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        relative = None
    return {"path":str(resolved), "projectRelativePath":relative, "sha256":_sha256(resolved)}


def _apply_drafting_density(model, density):
    factor = {"Compact":2.0, "Standard":1.0, "Detailed":0.5}[density]
    specification = model["draftingSpecification"]
    specification["horizontalTickM"] *= factor
    specification["verticalTickM"] *= factor
    specification["advancedDensity"] = density
    return model


def _write_refusal(run_dir, reason, request, **details):
    refusal = {"schemaVersion":"AdvancedJapanSectionRefusal-2.0", "passed":False,
               "reason":reason, "request":request.to_dict(), "dwgCreated":False,
               "fabricatedFallbackUsed":False, **details}
    refusal_path = Path(run_dir) / "typed_refusal.json"
    refusal_path.write_text(json.dumps(refusal, ensure_ascii=False, indent=2), encoding="utf-8")
    refusal["refusalPath"] = str(refusal_path)
    return refusal


def run_advanced_japan_section(project_root, request: AdvancedJapanSectionRequest, output_parent,
                               *, acquire_plan=None, native_dwg=True, location_resolver=None):
    root = Path(project_root).resolve(); request.validate()
    before = verify_frozen_basic_v1(root)
    if not before["passed"]: raise RuntimeError("frozen basic v1 boundary changed before advanced run")
    run_dir = Path(output_parent).resolve() / f"advanced_japan_{uuid4().hex[:12]}"
    plan_dir = run_dir / "plan"; section_dir = run_dir / "section"
    plan_dir.mkdir(parents=True, exist_ok=False); section_dir.mkdir()
    using_default_acquisition = acquire_plan is None
    acquisition = acquire_plan or _load_acquisition(root)
    try:
        acquisition(root, request.route(), request.sample_spacing_m, plan_dir,
                    "BilinearPixelCentres", root / "research/geologic_dwg_generation/cache/gsi")
    except Exception as exc:
        after = verify_frozen_basic_v1(root)
        if not after["passed"]: raise RuntimeError("frozen basic v1 boundary changed during failed acquisition")
        return _write_refusal(run_dir, "PlanEvidenceAcquisitionFailed", request,
                              errorType=type(exc).__name__, errorMessage=str(exc),
                              frozenBasicV1Before=before, frozenBasicV1After=after)
    plan_path = plan_dir / "plan_evidence_bundle.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if using_default_acquisition and "landformEvidence" not in plan:
        try:
            landform_bundle = acquire_landform_evidence(
                plan.get("terrainProfile", []),
                root / "research/geologic_dwg_generation/cache/gsi")
            plan["landformEvidenceBundle"] = landform_bundle
            plan["landformEvidence"] = landform_bundle["classificationEvidence"]
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            plan["landformEvidenceAcquisition"] = {
                "status":"Unavailable_FallbackToDemShape",
                "errorType":type(exc).__name__, "errorMessage":str(exc)}
    build_model, render, audit_model, classify, run_dwg, select_domain_model, classify_legend = _engine_imports(root)
    classification = classify_plan_advanced(plan, classify_legend)
    terrain_rows = plan.get("terrainProfile", [])
    terrain_morphology = classify_terrain_morphology(
        [row["stationM"] for row in terrain_rows],
        [row["elevationM"] for row in terrain_rows],
        landform_evidence=plan.get("landformEvidence"))
    terrain_texture_audit = None
    if terrain_morphology["primaryClass"] in {"MountainousRelief", "NarrowValleyOrGorge"}:
        terrain_texture_audit = audit_natural_terrain_texture(
            [row["stationM"] for row in terrain_rows],
            [row["elevationM"] for row in terrain_rows],
            synthetic_test_only=not using_default_acquisition)
        if not terrain_texture_audit["passed"]:
            return _write_refusal(run_dir, "NaturalTerrainResolutionRejected", request,
                                  terrainMorphology=terrain_morphology,
                                  terrainTextureAudit=terrain_texture_audit,
                                  frozenBasicV1Before=before,
                                  frozenBasicV1After=verify_frozen_basic_v1(root))
    context_paths = []
    regional_input_path = plan_dir / "regional_lithology_input.json"
    context_inference = None
    advanced_profile = profile_for_domain(classification["geologicalDomain"])
    if advanced_profile is None and classification["geologicalDomain"] in SUPPORTED_DOMAINS:
        advanced_profile = broad_profile_for_domain(
            classification["geologicalDomain"],
            select_domain_model(classification["geologicalDomain"]))
    if classification["geologicalDomain"] == "ArtificiallyModifiedTerrain":
        combined_evidence = {"sampleEvidence":[]}
        context_warnings = []
        context_length = min(20000.0, max(5000.0, request.length_m * 8.0))
        bearings = [request.azimuth_degrees, (request.azimuth_degrees+60.0)%360.0,
                    (request.azimuth_degrees+120.0)%360.0]
        for index, bearing in enumerate(bearings):
            context_dir = run_dir / f"context_{index+1}"
            context_dir.mkdir()
            context_request = AdvancedJapanSectionRequest(
                request.center_longitude, request.center_latitude, context_length, bearing,
                max(25.0, request.sample_spacing_m), request.seed, request.contact_lines, False)
            context_path = context_dir / "plan_evidence_bundle.json"
            warning = None
            try:
                acquisition(root, context_request.route(), context_request.sample_spacing_m, context_dir,
                            "BilinearPixelCentres", root / "research/geologic_dwg_generation/cache/gsi")
            except Exception as exc:
                if context_path.is_file():
                    warning = {"transect":index+1, "type":type(exc).__name__, "message":str(exc),
                               "evidenceBundleRecovered":True}
                else:
                    return _write_refusal(run_dir, "SurroundingEvidenceAcquisitionFailed", request,
                                          errorType=type(exc).__name__, errorMessage=str(exc),
                                          failedTransect=index+1, classification=classification)
            try:
                context_plan = json.loads(context_path.read_text(encoding="utf-8"))
                evidence = context_evidence_from_plan(context_plan, classify_legend)
                combined_evidence["sampleEvidence"].extend(evidence["sampleEvidence"])
                # Preserve actual source labels, not only the inferred domain.
                neighborhood = plan.setdefault("regionalBedrockNeighborhood", {"samples":[]})
                neighborhood["samples"].extend({**sample, "contextTransect":index+1}
                    for sample in context_plan.get("surfaceGeology", {}).get("samples", []))
                context_paths.append(context_path)
                if warning: context_warnings.append(warning)
            except Exception as exc:
                return _write_refusal(run_dir, "SurroundingEvidenceAcquisitionFailed", request,
                                      errorType=type(exc).__name__, errorMessage=str(exc),
                                      failedTransect=index+1, classification=classification)
        context_inference = infer_natural_domain(combined_evidence)
        context_inference.update({"contextRouteLengthMPerTransect":context_length,
                                  "supportTransectCount":3, "supportAzimuthsDegrees":bearings,
                                  "terrainElevationUsedForInference":False,
                                  "acquisitionWarnings":context_warnings})
        if context_inference["passed"]:
            inferred = context_inference["inferredNaturalDomain"]
            advanced_profile = contextual_profile_for_domain(inferred, select_domain_model(inferred))
        if advanced_profile is None:
            return _write_refusal(run_dir, "UnderlyingNaturalDomainUnavailable", request,
                                  classification=classification, contextInference=context_inference)
    if classification["geologicalDomain"] not in SUPPORTED_DOMAINS:
        if classification["geologicalDomain"] != "ArtificiallyModifiedTerrain" or advanced_profile is None:
            return _write_refusal(run_dir, "UnsupportedOrAmbiguousGeologicalDomain", request,
                                  classification=classification,
                                  frozenBasicV1Before=before,
                                  frozenBasicV1After=verify_frozen_basic_v1(root))
    advanced_profile = condition_profile_for_terrain(
        advanced_profile, terrain_morphology, request.length_m)
    selection_domain = (context_inference or {}).get(
        "inferredNaturalDomain", classification["geologicalDomain"])
    if selection_domain == "UnconsolidatedSedimentTerrain" and using_default_acquisition:
        if not resolve_regional_bedrock(plan)["candidates"]:
            plan["regionalBedrockNeighborhood"] = acquire_bedrock_neighborhood(plan)
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        write_and_load_regional_dataset(plan, regional_input_path)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        advanced_profile = select_evidence_bounded_lithologies(
            advanced_profile, selection_domain, plan)
    except (ValueError, OSError) as exc:
        return _write_refusal(run_dir, "RegionalLithologyInputRejected", request,
            errorType=type(exc).__name__, errorMessage=str(exc),
            frozenBasicV1Before=before, frozenBasicV1After=verify_frozen_basic_v1(root))
    model = build_model(plan, seed=request.seed, regional_profile=advanced_profile)
    if request.route_endpoints is not None:
        resolver=location_resolver or resolve_route_locations
        if not using_default_acquisition and location_resolver is None:
            # Offline fixtures never silently contact a live place service.
            def unavailable(_url):raise ValueError("SyntheticAcquisition_NoLivePlaceLookup")
            model["routeLocation"]=resolver(request.route(),terrain_rows,fetch=unavailable)
        else:model["routeLocation"]=resolver(request.route(),terrain_rows)
        model["routeLocation"]["routeLonLat"]=request.route()
    model["advancedEnglishUnitLabels"] = dict((advanced_profile or {}).get("englishUnitLabels", {}))
    model["planGeologicalDomainClassification"] = classification
    model["terrainMorphologyClassification"] = terrain_morphology
    model["terrainTextureAudit"] = terrain_texture_audit
    model["lithologySelection"] = advanced_profile["lithologySelection"]
    model["faciesMetadata"] = advanced_profile.get("faciesMetadata", [])
    model["terminologyCurrencyAudit"] = advanced_profile.get("terminologyCurrencyAudit", {})
    model["faciesArchitecture"] = advanced_profile.get("faciesArchitecture", {})
    model["majorLithologyEvidence"] = advanced_profile.get("majorLithologyEvidence", {})
    model["regionalLithologyInput"] = plan["regionalLithologyInput"]
    model["regionalLithologyInputFile"] = plan["regionalLithologyInputFile"]
    model["regionalLithologySelection"] = advanced_profile.get("regionalLithologySelection", {})
    model["regionalBedrockEvidence"] = advanced_profile.get("regionalBedrockEvidence", {})
    model["burialConditioning"] = advanced_profile.get("burialConditioning", [])
    model["effectiveLithologyDiversityAudit"] = advanced_profile.get(
        "effectiveLithologyDiversityAudit", {})
    normalize_model_added_lithologies(model)
    _apply_drafting_density(model, request.drafting_density)
    apply_advanced_contact_geometry(model)
    apply_regional_bedrock_geometry(model)
    model["regionalBedrockAudit"] = audit_regional_bedrock(model)
    model["modelAudit"] = audit_model(model)
    model["faciesPortrayalAudit"] = audit_facies_portrayal(model)
    model["advancedContactGeometryAudit"] = audit_advanced_contact_geometry(model)
    model["contactRangeEnsembleAudit"] = audit_contact_sampler_implementation()
    require_current_publication_terminology(model)
    if (not model["regionalBedrockAudit"]["passed"] or not model["modelAudit"]["passed"] or
            not model["faciesPortrayalAudit"]["passed"] or
            not model["advancedContactGeometryAudit"]["passed"] or
            not model["contactRangeEnsembleAudit"]["passed"]):
        return _write_refusal(run_dir, "AdvancedContactGeometryRejected", request,
                              modelAudit=model["modelAudit"],
                              regionalBedrockAudit=model["regionalBedrockAudit"],
                              faciesPortrayalAudit=model["faciesPortrayalAudit"],
                              advancedContactGeometryAudit=model["advancedContactGeometryAudit"],
                              contactRangeEnsembleAudit=model["contactRangeEnsembleAudit"],
                              frozenBasicV1Before=before,
                              frozenBasicV1After=verify_frozen_basic_v1(root))
    model["advancedExtension"] = {"schemaVersion":"AdvancedJapanSection-2.0",
                                  "basicV1Modified":False, "request":request.to_dict(),
                                  "domainSupport":"BroadPriorOnly",
                                  "advancedProfileId":None if advanced_profile is None else advanced_profile["profileId"],
                                  "contextInference":context_inference,
                                  "terrainMorphology":terrain_morphology}
    image = None
    # Rendering executes the shared pre-output gate and writes the adjacent model.
    rendered = render(model, section_dir / "section_preview.png", contact_lines=request.contact_lines)
    model["advancedPreviewLayoutAudit"] = finalize_advanced_preview_layout(model, rendered)
    # The shared renderer writes model.json before the Advanced-V2-only
    # presentation pass. Persist the final audit without touching Basic V1.
    (section_dir / "model.json").write_text(
        json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    # The renderer is also the pre-output visual/compliance gate.  Keep its
    # product as audit evidence even when the caller does not promote PNG as a
    # requested deliverable; advanced runs must remain fully reviewable.
    image = rendered
    model_path = section_dir / "model.json"
    try:
        contract_path = write_advanced_dwg_handoff(
            model, section_dir / "native_dwg_contract_envelope.json")
    except ValueError as exc:
        return _write_refusal(
            run_dir, "AdvancedDwgContractRejected", request,
            errorType=type(exc).__name__, errorMessage=str(exc),
            modelAudit=model.get("modelAudit"),
            faciesPortrayalAudit=model.get("faciesPortrayalAudit"),
            advancedContactGeometryAudit=model.get("advancedContactGeometryAudit"),
            advancedPreviewLayoutAudit=model.get("advancedPreviewLayoutAudit"),
            contractGateFindings=getattr(exc, "findings", []),
            frozenBasicV1Before=before,
            frozenBasicV1After=verify_frozen_basic_v1(root))
    dwg = report = None
    if native_dwg:
        dwg, report = run_dwg(root, contract_path, f"Japan_AdvancedV2_{request.seed}_{run_dir.name[-12:]}")
    after = verify_frozen_basic_v1(root)
    if not after["passed"]: raise RuntimeError("frozen basic v1 boundary changed during advanced run")
    artifacts = [plan_path, regional_input_path] + context_paths + [model_path, contract_path] + \
                ([image] if image else []) + ([dwg, report] if dwg else [])
    source_reuse = [
        {"sourceId":"GSI-ELEVATION-TILE", "authority":"Geospatial Information Authority of Japan",
         "termsUrl":"https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html",
         "use":"DEM-derived terrain; processed and attributed"},
        {"sourceId":"GSJ-SEAMLESS-V2-API", "authority":"Geological Survey of Japan, AIST",
         "termsUrl":"https://www.gsj.jp/license/index.html",
         "use":"Mapped surface-geology evidence; processed, not vertically projected"}]
    if plan.get("landformEvidenceBundle"):
        source_reuse.append(
            {"sourceId":"GSI-LANDFORM-VECTOR-2026",
             "authority":"Geospatial Information Authority of Japan",
             "termsUrl":"https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html",
             "use":"Natural/artificial landform prior; does not authorize subsurface contacts"})
    manifest = {"schemaVersion":"AdvancedJapanSectionRun-2.1", "passed":True,
                "decision":"Experimental", "realRegionAuthorized":False,
                "request":request.to_dict(), "domainClassification":classification,
                "terrainMorphologyClassification":terrain_morphology,
                "contextInference":context_inference,
                "frozenBasicV1Before":before, "frozenBasicV1After":after,
                "primaryArtifact":"NativeDwg" if dwg else "IntegrityBoundDwgContract",
                "pngRole":"SecondaryVisualCheck" if request.png_preview else "RetainedAuditEvidence",
                "sourceReuseBoundary":source_reuse,
                "artifacts":[_artifact_record(root, path) for path in artifacts],
                "limitations":["Broad mapped-domain prior; not a local stratigraphic interpretation",
                               "No borehole or structural control unless separately supplied",
                               "Not for investigation, design or construction"]}
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifestPath"] = str(manifest_path)
    return manifest
