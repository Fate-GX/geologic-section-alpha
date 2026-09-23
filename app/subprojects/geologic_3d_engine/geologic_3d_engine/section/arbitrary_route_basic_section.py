"""Render a region-neutral basic section from a PlanEvidenceBundle.

Mapped GSJ units constrain only the surface trace. Their shallow vertical
continuation is deliberately marked synthetic; terrain alone never selects
subsurface lithology.
"""
from __future__ import annotations
import hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from ..modeling.terrain_surface_model import build_terrain_surface_model
from ..modeling.basic_provider import BasicCorrelatedLithologyProvider
from ..modeling.provider_contract import invoke_lithology_provider
from ..modeling.terrain_lithology_composer import compose_terrain_and_lithology
from ..modeling.regional_background_architecture import (apply_volcanic_paleosurface_stack,
  apply_deformed_sedimentary_stack,apply_plutonic_weathering_mass)
from ..modeling.domain_model_library import select_domain_model
from .synthetic_event_adapter import (apply_synthetic_event_architecture,
                                      apply_conservative_regional_architecture)
from ..validation.geological_prior_gate import evaluate_geological_priors
from ..validation.terrain_surface_gate import audit_route_terrain
from ..validation.domain_realism_gate import audit_domain_model_realism
from .geological_domain_classifier import classify_plan_geological_domain
from ..profiles.neighbor_evidence_inference import (infer_from_neighboring_evidence,
                                                    infer_from_national_evidence_index)

def _font(size):
    path=Path("C:/Windows/Fonts/meiryo.ttc")
    return ImageFont.truetype(str(path),size) if path.exists() else ImageFont.load_default()

def _validate_plan(plan):
    if not isinstance(plan,dict) or plan.get("schemaVersion")!="PlanEvidenceBundle-1.0":
        raise ValueError("PlanEvidenceBundle-1.0 is required")
    rows=plan.get("terrainProfile")
    if not isinstance(rows,list) or len(rows)<2:raise ValueError("terrain profile is required")
    stations=np.asarray([r.get("stationM") for r in rows],float)
    terrain=np.asarray([r.get("elevationM") for r in rows],float)
    if not np.isfinite(stations).all() or not np.isfinite(terrain).all() or stations[0]!=0 or np.any(np.diff(stations)<=0):
        raise ValueError("terrain profile must be finite and ordered")
    geology=plan.get("surfaceGeology")
    if not isinstance(geology,dict) or not geology.get("samples"):
        raise ValueError("mapped surface geology samples are required")
    return rows,stations,terrain,geology

def _nice_tick(span,minimum_count=4,maximum_count=10):
    if not math.isfinite(span) or span<=0:raise ValueError("positive finite axis span required")
    raw=span/6.0;power=10.0**math.floor(math.log10(raw))
    choices=[1.0,2.0,2.5,5.0,10.0]
    candidates=[v*power for v in choices]
    valid=[v for v in candidates if minimum_count<=span/v<=maximum_count]
    return min(valid,key=lambda v:abs(span/v-6.0)) if valid else min(candidates,key=lambda v:abs(span/v-6.0))

def _direction_labels(route):
    if not isinstance(route,list) or len(route)<2:return ("始点","終点")
    lon0,lat0=map(float,route[0]);lon1,lat1=map(float,route[-1])
    dx=(lon1-lon0)*math.cos(math.radians((lat0+lat1)/2));dy=lat1-lat0
    if abs(dx)>=abs(dy):return (("西","東") if dx>=0 else ("東","西"))
    return (("南","北") if dy>=0 else ("北","南"))

def _drafting_specification(model,zmin,zmax):
    length=float(model["stationsM"][-1]);directions=_direction_labels(model.get("routeLonLat"))
    return {"standardId":"ProjectGeologicalCrossSectionRaster-1.0",
      "sourceRule":"cross_section_drafting_and_publication_rules.md",
      "sectionId":"A–A′","leftDirection":directions[0],"rightDirection":directions[1],
      "actualSectionLengthM":length,"horizontalTickM":_nice_tick(length),
      "verticalTickM":_nice_tick(zmax-zmin),
      "elevationDatum":"GSI_DEM_Elevation_VerticalDatumUnverified",
      "elevationUnits":"m","bilateralElevationTicks":True,
      "explicitVerticalExaggeration":True,"graphicalScale":True,
      "syntheticDisclosure":True,"contactLineForemost":True}

def audit_drafting_specification(spec):
    required={"standardId","sourceRule","sectionId","leftDirection","rightDirection",
      "actualSectionLengthM","horizontalTickM","verticalTickM","elevationDatum",
      "elevationUnits","bilateralElevationTicks","explicitVerticalExaggeration",
      "graphicalScale","syntheticDisclosure","contactLineForemost"}
    errors=[]
    if not isinstance(spec,dict) or not required<=set(spec):errors.append("IncompleteDrawingSpecification")
    else:
      for key in ("actualSectionLengthM","horizontalTickM","verticalTickM"):
        if not isinstance(spec[key],(int,float)) or not math.isfinite(spec[key]) or spec[key]<=0:
          errors.append("InvalidDrawingScale:"+key)
      for key in ("bilateralElevationTicks","explicitVerticalExaggeration","graphicalScale",
                  "syntheticDisclosure","contactLineForemost"):
        if spec[key] is not True:errors.append("RequiredDrawingFeatureDisabled:"+key)
      if spec["elevationUnits"]!="m":errors.append("UnsupportedElevationUnit")
    return {"passed":not errors,"errors":errors,"checkedBeforeOutput":True,
      "gate":"GeologicalCrossSectionDraftingStandard"}

def audit_arbitrary_route_basic_model(model):
    layers=model.get("composition",{}).get("layersTopDown",[]);errors=[]
    if len(layers)<5:errors.append("TooFewRenderedLithologies")
    for index,layer in enumerate(layers):
        thickness=np.asarray(layer.get("thicknessM",[]),float)
        invalid=(thickness.size==0 or not np.isfinite(thickness).all() or np.any(thickness<0) or
                 (np.any(thickness<=1e-9) and not layer.get("allowPinchout")) or
                 not np.any(thickness>1e-9))
        if invalid:
            errors.append(f"NonPositiveThickness:{index}")
    for index,(upper,lower) in enumerate(zip(layers,layers[1:])):
        if upper.get("bottomElevationM")!=lower.get("topElevationM"):
            errors.append(f"UnsharedContact:{index}")
    if model.get("shallowBodyRole")!="SyntheticConformableFacies_NotMappedUnitExtension":
        errors.append("MappedSurfaceIllegallyExtendedIntoSubsurface")
    event_log=model.get("syntheticEventArchitecture",{}).get("eventLog",[])
    architecture=model.get("syntheticEventArchitecture",{})
    conservative=architecture.get("architectureMode")=="ConservativeRegionalPrior_NoLocalizedEvents"
    required=({"RegionalPriorNoLocalizedEvent"} if conservative else
              {"Erosion","StratifiedErosionFill"})
    present={v.get("eventType") for v in event_log}
    if not required<=present:errors.append("EventEngineNotConnected")
    if not conservative and not any(not flag for body in model.get("syntheticEventArchitecture",{}).get("renderBodies",[])
                                    for flag in body.get("activeMask",[])):
        errors.append("NoTruncationOrPinchoutProduced")
    parallelism=audit_contact_terrain_parallelism(model)
    background_type=model.get("composition",{}).get("backgroundArchitecture",{}).get("type")
    parallelism_required=background_type!="PlutonicWeatheringMass"
    if conservative and parallelism_required and not parallelism["passed"]:
        errors.append("ExcessiveTerrainParallelContactArchitecture")
    surface_audit=audit_superficial_geology(model)
    if not surface_audit["passed"]:errors.extend(surface_audit["errors"])
    domain_audit=audit_domain_model_realism(model)
    if not domain_audit["passed"]:errors.extend(domain_audit["errors"])
    return {"passed":not errors,"errors":errors,"lithologyCount":len(layers),
      "positiveThickness":not any(x.startswith("NonPositive") for x in errors),
      "positiveThicknessOrExplicitPinchout":not any(x.startswith("NonPositive") for x in errors),
      "sharedContacts":not any(x.startswith("Unshared") for x in errors),
      "mappedSurfaceVerticalProjectionCount":0 if "MappedSurfaceIllegallyExtendedIntoSubsurface" not in errors else None,
      "eventEngineConnected":"EventEngineNotConnected" not in errors,
      "nonConformableGeometryPresent":False if conservative else "NoTruncationOrPinchoutProduced" not in errors,
      "localizedEventSuppressedByPriorGate":conservative,
      "terrainParallelismGateApplicable":parallelism_required,
      "contactTerrainParallelismAudit":parallelism,"superficialGeologyAudit":surface_audit,
      "domainModelRealismAudit":domain_audit}

def audit_superficial_geology(model):
    layers=model.get("composition",{}).get("layersTopDown",[]);errors=[]
    background=model.get("composition",{}).get("backgroundArchitecture",{})
    if background.get("type") in {"VolcanicPaleosurfaceStack","DeformedSedimentaryStack",
                                  "PlutonicWeatheringMass"}:
        if not layers:errors.append("MissingSurfaceCover")
        else:
            cover=layers[0];thickness=np.asarray(cover.get("thicknessM",[]),float)
            limit=float(background.get("surfaceCoverMaximumM",5.0))
            if thickness.size==0 or np.max(thickness)>limit+1e-9:
                errors.append("SurfaceCoverExceedsMaximumThickness")
            if "WEATHERED" in cover.get("unitId",""):
                errors.append("WeatheringIllegallyRepresentedAsSeparateThickLithology")
        if background.get("weatheringRepresentation") not in {
                "ParentRockState_NotSeparateThickBody",
                "GradedParentRockState_NotStratigraphicBeds"}:
            errors.append("MissingWeatheringStatePolicy")
    return {"passed":not errors,"errors":errors,"checkedBeforeOutput":True}

def audit_contact_terrain_parallelism(model,*,correlation_limit=.995,
                                      relative_residual_limit=.15):
    """Reject a stack whose contacts are merely translated terrain copies."""
    terrain=np.asarray(model.get("terrainElevationM",[]),float)
    bodies=model.get("syntheticEventArchitecture",{}).get("renderBodies",[])
    if terrain.size<3 or not np.isfinite(terrain).all() or np.ptp(terrain)<=0:
        return {"passed":False,"errors":["TerrainUnavailableForParallelismAudit"]}
    basement_id=model.get("composition",{}).get("layersTopDown",[{}])[-1].get("unitId")
    findings=[]
    for body in bodies:
        if body.get("bodyRole")!="PrimaryBody" or body.get("unitId")==basement_id:continue
        contact=np.asarray(body.get("bottomElevationM",[]),float)
        if contact.shape!=terrain.shape or not np.isfinite(contact).all():continue
        correlation=float(np.corrcoef(terrain,contact)[0,1])
        residual_ratio=float(np.ptp(contact-terrain)/np.ptp(terrain))
        copied=bool(correlation>=correlation_limit and residual_ratio<=relative_residual_limit)
        findings.append({"unitId":body["unitId"],"terrainContactCorrelation":correlation,
                         "relativeResidualRelief":residual_ratio,"terrainCopyLike":copied})
    copied_count=sum(row["terrainCopyLike"] for row in findings)
    allowed=max(1,len(findings)//3)
    return {"passed":copied_count<=allowed,"evaluatedContactCount":len(findings),
            "terrainCopyLikeContactCount":copied_count,
            "maximumAllowedCopyLikeContacts":allowed,
            "correlationLimit":correlation_limit,
            "relativeResidualLimit":relative_residual_limit,"contacts":findings,
            "errors":[] if copied_count<=allowed else ["TooManyTerrainCopyLikeContacts"]}

def preflight_arbitrary_route_render(model,contact_lines):
    """Fail before file creation when the requested drawing violates its contract."""
    errors=[];model_audit=audit_arbitrary_route_basic_model(model)
    if not model_audit["passed"]:errors.extend(model_audit["errors"])
    stations=model.get("stationsM",[])
    bodies=model.get("syntheticEventArchitecture",{}).get("renderBodies",[])
    boundaries=[];basement_id=model.get("composition",{}).get("layersTopDown",[{}])[-1].get("unitId")
    architecture_type=model.get("composition",{}).get("backgroundArchitecture",{}).get("type")
    for body in bodies:
        if body.get("bodyRole")=="PrimaryBody" and body.get("unitId")!=basement_id:
            boundaries.append({"unitId":body["unitId"],"surface":"bottomElevationM",
              "boundaryClass":"WeatheringStateFront" if architecture_type=="PlutonicWeatheringMass"
                              else "LithologyContactOrUnconformity"})
        elif body.get("bodyRole")=="ReplacementLens":
            boundaries.extend([
              {"unitId":body["unitId"],"surface":"topElevationM","boundaryClass":"LensBoundary"},
              {"unitId":body["unitId"],"surface":"bottomElevationM","boundaryClass":"LensBoundary"}])
    for item in boundaries:
        values=next(v for v in bodies if v["unitId"]==item["unitId"])[item["surface"]]
        if len(values)!=len(stations) or not np.isfinite(np.asarray(values,float)).all():
            errors.append("InvalidLithologyBoundary:"+item["unitId"]+":"+item["surface"])
    if contact_lines=="Show" and not boundaries:errors.append("MissingLithologyBoundaryLines")
    drafting=model.get("draftingSpecification")
    drafting_audit=audit_drafting_specification(drafting)
    if not drafting_audit["passed"]:errors.extend(drafting_audit["errors"])
    return {"passed":not errors,"errors":errors,"checkedBeforeOutput":True,
      "designPolicy":"SeparatedTerrainLithology_EventEngine_NoMappedVerticalProjection",
      "contactLinesRequested":contact_lines,"lithologyBoundaryLineCount":len(boundaries),
      "boundaries":boundaries,"modelAudit":model_audit,"draftingAudit":drafting_audit}

def audit_terrain_lithology_ensemble(stations,terrain,request,*,sample_count=64):
    """Test systematic dependence using many realizations, not iid p-values.

    Both profiles are spatially autocorrelated, so a conventional Pearson
    significance test on one realization is not a valid independence test.
    """
    correlations=[]
    for seed in range(1000,1000+sample_count):
        probe={**request,"seed":seed}
        generated=invoke_lithology_provider(BasicCorrelatedLithologyProvider(),stations.tolist(),probe)
        correlations.append([float(np.corrcoef(terrain,np.asarray(v["thicknessM"],float))[0,1])
          for v in generated["layersTopDown"]])
    matrix=np.asarray(correlations,float)
    means=matrix.mean(axis=0);positive=(matrix>0).mean(axis=0);p95=np.quantile(abs(matrix),.95,axis=0)
    passed=bool(np.max(abs(means))<=.25 and np.all((positive>=.15)&(positive<=.85)))
    return {"passed":passed,"method":"FixedTerrain_MultipleIndependentSeeds_AutocorrelationAwareDiagnostic",
      "sampleCount":sample_count,"meanPearsonByLayer":means.tolist(),
      "positiveFractionByLayer":positive.tolist(),"absolutePearsonP95ByLayer":p95.tolist(),
      "singleRealizationPValuesUsed":False}

def build_arbitrary_route_basic_model(plan,*,seed,shallow_mean_m=12.0,substrate_mean_m=70.0,
                                      correlation_range_m=450.0,log_std=.14,regional_profile=None,
                                      neighboring_evidence=None,neighbor_support_radius_m=50000.0,
                                      national_evidence_index=None):
    rows,stations,terrain,geology=_validate_plan(plan)
    domain_classification=classify_plan_geological_domain(plan)
    prior_decision=evaluate_geological_priors(regional_profile)
    if not prior_decision["passed"]:
        raise ValueError("geological prior gate rejected the regional profile")
    # The plan sampler normally produces regular stations. Regrid explicitly
    # when the final endpoint creates a non-regular remainder.
    regular=np.linspace(0,float(stations[-1]),len(stations))
    regular_terrain=np.interp(regular,stations,terrain)
    terrain_audit=audit_route_terrain(plan,regular,regular_terrain)
    if not terrain_audit["passed"]:
        raise ValueError("terrain surface gate rejected the route profile: "+",".join(terrain_audit["errors"]))
    dem_layer=next((x for x in plan.get("layers",[]) if x.get("evidence_kind")=="DEM"),None)
    source_hash=(dem_layer or {}).get("content_sha256") or hashlib.sha256(
        json.dumps(rows,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    terrain_model=build_terrain_surface_model(
      [{"stationM":float(s),"elevationM":float(z)} for s,z in zip(regular,regular_terrain)],
      source_id=(dem_layer or {}).get("source_id","PLAN-DEM"),source_sha256=source_hash,
      sampling_method="PlanEvidenceRouteProfile_LinearRegrid")
    # This generic facies stack is intentionally independent of mapped surface
    # identity. It is a replaceable visual hypothesis, never a local unit order.
    selected_domain_model=select_domain_model(domain_classification["geologicalDomain"])
    # Mapped surface geology can choose a broad reusable background prior, but
    # cannot by itself authorize a local valley, fault, fold or intrusion.
    if regional_profile is None and selected_domain_model["selectionStatus"]=="ReusableDomainPriorSelected":
        prior_decision={**prior_decision,
          "architectureMode":"ConservativeRegionalPrior_NoLocalizedEvents",
          "localizedEventsAuthorized":False,"safeDegradationApplied":True,
          "domainPriorSelectionDoesNotAuthorizeLocalizedEvents":True}
    facies=(regional_profile or {}).get("substrateFacies") or selected_domain_model.get("facies") or [
      ("SYN-REGOLITH","表層堆積物・風化帯（合成）",shallow_mean_m,"#d8c59d"),
      ("SYN-SAND-RICH","砂質堆積岩（合成）",18.0,"#e6c36a"),
      ("SYN-MUD-RICH","泥質堆積岩（合成）",24.0,"#9aa7a0"),
      ("SYN-GRAVEL-RICH","礫質堆積岩（合成）",32.0,"#b18b68"),
      ("SYN-VOLCANIC","火山岩類（合成）",44.0,"#8d7599"),
      ("SYN-BASEMENT","基盤岩類（合成）",substrate_mean_m,"#746c66")]
    facies=[tuple(v) for v in facies]
    background=(regional_profile or {}).get("backgroundArchitecture",{})
    architecture_type=background.get("architectureType") or selected_domain_model["architectureType"]
    required_domain={"VolcanicPaleosurfaceStack":"VolcanicTerrain",
      "PlutonicWeatheringMass":"PlutonicTerrain"}.get(architecture_type)
    if required_domain and domain_classification["geologicalDomain"]!=required_domain:
        raise ValueError("selected background architecture is incompatible with mapped geological domain")
    layer_controls=background.get("layerControls",{})
    request={"seed":seed,
      "rangeM":float(background.get("defaultCorrelationRangeM",correlation_range_m)),
      "logStd":float(background.get("defaultLogStd",log_std)),"layers":[
      {"unitId":unit,"normalizedLithology":label,"meanThicknessM":mean,"color":color,
       **({"rangeM":float(layer_controls[unit]["rangeM"]),
           "logStd":float(layer_controls[unit]["logStd"])} if unit in layer_controls else {})}
      for unit,label,mean,color in facies]}
    lithology=invoke_lithology_provider(BasicCorrelatedLithologyProvider(),regular.tolist(),request)
    independence=audit_terrain_lithology_ensemble(regular,regular_terrain,request)
    if not independence["passed"]:raise ValueError("terrain/lithology ensemble independence audit failed")
    composition=compose_terrain_and_lithology(terrain_model,lithology)
    if architecture_type=="VolcanicPaleosurfaceStack":
        composition=apply_volcanic_paleosurface_stack(
          composition,seed=seed,dip_degrees=float(background.get("regionalDipDegrees",-8.0)))
    elif architecture_type=="DeformedSedimentaryStack":
        composition=apply_deformed_sedimentary_stack(
          composition,seed=seed,dip_degrees=float(background.get("regionalDipDegrees",2.0)))
    elif architecture_type=="PlutonicWeatheringMass":
        composition=apply_plutonic_weathering_mass(composition,seed=seed)
    if prior_decision["architectureMode"]=="ConservativeRegionalPrior_NoLocalizedEvents":
        event_architecture=apply_conservative_regional_architecture(
          composition,regular,prior_decision=prior_decision)
    else:
        event_architecture=apply_synthetic_event_architecture(composition,regular,seed=seed,
          regional_profile=regional_profile)
    geo_samples=[]
    for sample in geology["samples"]:
        legend=sample.get("legend")
        geo_samples.append({"stationM":float(sample["stationM"]),"symbol":None if not legend else legend["symbol"],
          "lithologyJa":None if not legend else legend["lithology_ja"],
          "formationAgeJa":None if not legend else legend["formationAge_ja"],
          "color":None if not legend else "#"+legend["value"]})
    nearest=[]
    gs=np.asarray([x["stationM"] for x in geo_samples])
    for station in regular:
        index=int(np.argmin(abs(gs-station)));nearest.append(dict(geo_samples[index]))
    result={"schemaVersion":"ArbitraryRouteBasicSection-1.0","seed":seed,
      "routeLonLat":plan.get("routeLonLat"),"stationsM":regular.tolist(),"terrainElevationM":regular_terrain.tolist(),
      "terrainModel":terrain_model,"lithologyModel":lithology,"composition":composition,
      "terrainSurfaceAudit":terrain_audit,
      "planGeologicalDomainClassification":domain_classification,
      "domainModelSelection":{"classifiedDomain":domain_classification["geologicalDomain"],
        "selectedArchitecture":architecture_type,"selectionStatus":selected_domain_model["selectionStatus"],
        "compatibilityChecked":bool(required_domain),"compatible":not required_domain or
          domain_classification["geologicalDomain"]==required_domain},
      "syntheticEventArchitecture":event_architecture,
      "geologicalPriorDecision":prior_decision,
      "terrainLithologyIndependenceAudit":independence,
      "mappedSurfaceAtStations":nearest,"surfaceEvidenceRole":"MappedSurfaceConstraintOnly",
      "shallowBodyRole":"SyntheticConformableFacies_NotMappedUnitExtension",
      "deepBodyRole":"SyntheticBasementFilledToFrame","realRegionAuthorized":False,
      "renderingLithologies":[{"unitId":u,"label":label,"color":color} for u,label,_mean,color in facies]+([
       {"unitId":v["unitId"],"label":v["label"],"color":v["color"]}
       for v in regional_profile["fillFacies"]] if regional_profile and regional_profile.get("fillFacies") else [
       {"unitId":"SYN-VALLEY-BASAL","label":"礫質谷底堆積物（合成）","color":"#9a7655"},
       {"unitId":"SYN-VALLEY-MIXED","label":"砂泥質谷埋め堆積物（合成）","color":"#c9a765"},
       {"unitId":"SYN-VALLEY-FINE","label":"細粒谷埋め堆積物（合成）","color":"#b7ad8a"}]),
      "regionalPriorProfile":regional_profile,
      "decision":"Experimental","limitations":["No borehole constraint","No structure orientation constraint",
       "Mapped surface unit is not proof of generated subsurface geometry","Not for design use"]}
    if neighboring_evidence is not None and national_evidence_index is not None:
        raise ValueError("use either neighboring_evidence or national_evidence_index")
    if neighboring_evidence is not None or national_evidence_index is not None:
        route=plan.get("routeLonLat") or []
        target={"targetId":plan.get("routeId","ARBITRARY-ROUTE"),
                "geologicalProvince":(regional_profile or {}).get("geologicalProvince"),
                "ageInterval":(regional_profile or {}).get("ageInterval"),
                "environment":(regional_profile or {}).get("environment"),
                "routeLonLat":route}
        if national_evidence_index is not None:
            if len(route)<2:raise ValueError("route coordinates required for national evidence query")
            target.update({"longitude":sum(float(p[0]) for p in route)/len(route),
                           "latitude":sum(float(p[1]) for p in route)/len(route),
                           "ageApplicability":target["ageInterval"],
                           "environmentApplicability":target["environment"]})
            inference=infer_from_national_evidence_index(
                national_evidence_index,target,maximum_distance_m=neighbor_support_radius_m)
        else:
            inference=infer_from_neighboring_evidence(target,neighboring_evidence,
                                                       maximum_distance_m=neighbor_support_radius_m)
        result["neighborEvidenceInference"]=inference
        if not inference["passed"]:
            result["limitations"].append("No geologically applicable neighboring evidence")
    provisional_boundaries=[np.asarray(v["bottomElevationM"],float) for v in composition["layersTopDown"]]
    provisional_zmin=float(provisional_boundaries[-1].min()-20.0)
    provisional_zmax=float(regular_terrain.max()+30.0)
    result["draftingSpecification"]=_drafting_specification(result,provisional_zmin,provisional_zmax)
    result["modelAudit"]=audit_arbitrary_route_basic_model(result)
    if not result["modelAudit"]["passed"]:raise ValueError("basic section model invariant failed")
    return result

def render_arbitrary_route_basic_section(model,target,*,contact_lines="Show"):
    if contact_lines not in {"Show","Hide"}:raise ValueError("contact_lines must be Show or Hide")
    preflight=preflight_arbitrary_route_render(model,contact_lines)
    if not preflight["passed"]:raise ValueError("pre-output compliance audit failed")
    model["preOutputComplianceAudit"]=preflight
    x=np.asarray(model["stationsM"]);terrain=np.asarray(model["terrainElevationM"])
    layers=model["composition"]["layersTopDown"]
    width,height=1800,1160;left,right,top,bottom=130,1710,178,750
    all_layers=model["composition"]["layersTopDown"]
    boundaries=[np.asarray(v["bottomElevationM"]) for v in all_layers]
    xmin,xmax=0,float(x[-1]);zmin=float(boundaries[-1].min()-20);zmax=float(terrain.max()+30)
    def pt(a,z):return (left+(a-xmin)/(xmax-xmin)*(right-left),bottom-(z-zmin)/(zmax-zmin)*(bottom-top))
    image=Image.new("RGB",(width,height),"#f4f6f8");draw=ImageDraw.Draw(image)
    draw.rectangle((left,top,right,bottom),fill="white",outline="#607080",width=2)
    definitions={v["unitId"]:v for v in model["renderingLithologies"]}
    bodies=model["syntheticEventArchitecture"]["renderBodies"]
    # Basement first and open downward, then old bodies bottom-up and young fill.
    basement_id=model["composition"]["layersTopDown"][-1]["unitId"]
    basement=next(v for v in bodies if v["unitId"]==basement_id)
    draw.polygon([pt(a,z) for a,z in zip(x,basement["topElevationM"])]+[pt(x[-1],zmin),pt(x[0],zmin)],
      fill=definitions[basement_id]["color"])
    primary=[v for v in bodies if v["bodyRole"]=="PrimaryBody" and v["unitId"]!=basement_id]
    def active_runs(body):
        active=list(body.get("activeMask",[True]*len(x)));runs=[];start=None
        for index,enabled in enumerate(active+[False]):
            if enabled and start is None:start=index
            if not enabled and start is not None:
                end=index-1
                if end>=start:runs.append((max(0,start-1),min(len(x)-1,end+1),start,end))
                start=None
        return runs
    for body in reversed(primary):
        for closure_start,closure_end,start,end in active_runs(body):
            if end>=start:
                draw.polygon([pt(a,z) for a,z in zip(x[closure_start:closure_end+1],body["topElevationM"][closure_start:closure_end+1])]+[
                  pt(a,z) for a,z in zip(x[closure_start:closure_end+1],body["bottomElevationM"][closure_start:closure_end+1])][::-1],
                  fill=definitions[body["unitId"]]["color"])
    values=model["mappedSurfaceAtStations"]
    # Mapped identity is confined to the terrain trace and never drawn down.
    draw.line([pt(a,z) for a,z in zip(x,terrain)],fill="#111820",width=7)
    run_start=0
    for i in range(1,len(values)+1):
        if i==len(values) or values[i]["symbol"]!=values[run_start]["symbol"]:
            end=max(i-1,run_start)
            if end==run_start and end+1<len(x):end+=1
            draw.line([pt(a,z) for a,z in zip(x[run_start:end+1],terrain[run_start:end+1])],
                      fill=values[run_start]["color"] or "#cfcfcf",width=4)
            run_start=i
    # Geological contacts are the foremost drawing layer.  Keeping this pass
    # last prevents shallow, gently sloping contacts from being hidden by a
    # polygon edge, terrain trace or mapped-surface evidence line.
    if contact_lines=="Show":
        def dashed(points,color,width,dash=11,gap=7):
            for a,b in zip(points,points[1:]):
                ax,ay=a;bx,by=b;length=math.hypot(bx-ax,by-ay)
                if length<=0:continue
                position=0.0
                while position<length:
                    end=min(length,position+dash);t0=position/length;t1=end/length
                    draw.line((ax+(bx-ax)*t0,ay+(by-ay)*t0,
                               ax+(bx-ax)*t1,ay+(by-ay)*t1),fill=color,width=width)
                    position+=dash+gap
        for item in preflight["boundaries"]:
            body=next(v for v in bodies if v["unitId"]==item["unitId"])
            boundary_values=np.asarray(body[item["surface"]],float)
            for closure_start,closure_end,start,end in active_runs(body):
                if end>start:
                    points=[pt(a,z) for a,z in zip(x[closure_start:closure_end+1],
                      boundary_values[closure_start:closure_end+1])]
                    if item["boundaryClass"]=="WeatheringStateFront":dashed(points,"#433a32",3)
                    else:draw.line(points,fill="#211d1a",width=3)
    transitions=[]
    for i in range(1,len(values)):
        if values[i]["symbol"]!=values[i-1]["symbol"]:
            transitions.append(i)
    profile=model.get("regionalPriorProfile") or {}
    title=model.get("displayTitle") or profile.get("displayTitle","任意測線・合成地質断面図")
    spec=model["draftingSpecification"]
    draw.text((80,28),f"{spec['sectionId']}  {title}（測線実長 {xmax:.1f} m）",font=_font(31),fill="#203649")
    inference=model.get("neighborEvidenceInference")
    inference_note=(inference.get("drawingDisclosureJa") if isinstance(inference,dict) and inference.get("passed") else
                    "地下は地表地質区分と汎用地質規則に基づく合成仮説（実測断面ではない）")
    draw.text((80,80),"黒線=DEM地形・地表色=GSJ地表地質 ／ "+inference_note,
              font=_font(22),fill="#8a3b12")
    draw.text((80,112),"標高基準：GSI DEM標高（鉛直基準の個別検証なし）／ 疑似データ・調査設計施工には使用不可",
              font=_font(17),fill="#8a3b12")
    domain=model.get("planGeologicalDomainClassification",{})
    selection=model.get("domainModelSelection",{})
    domain_ja={"VolcanicTerrain":"火山岩地域","PlutonicTerrain":"深成岩地域",
      "MetamorphicBelt":"変成帯","AccretionaryComplex":"付加体",
      "SedimentaryRockTerrain":"堆積岩地域","UnconsolidatedSedimentTerrain":"未固結堆積地域",
      "ArtificiallyModifiedTerrain":"人工改変地域","MixedGeologicalDomain":"複合地質地域",
      "Unresolved":"判別不能"}.get(domain.get("geologicalDomain"),domain.get("geologicalDomain","未判定"))
    landform_ja={"MountainousRelief":"山岳地形","HillyRelief":"丘陵地形",
                 "LowRelief":"低起伏地形"}.get(domain.get("landformContext"),"地形未判定")
    architecture_ja={"VolcanicPaleosurfaceStack":"火山古地形面モデル",
                     "DeformedSedimentaryStack":"変形堆積層モデル",
                     "PlutonicWeatheringMass":"深成岩風化帯モデル",
                     "DefaultRelativeDepthStack":"標準相対層厚モデル"}.get(
                       selection.get("selectedArchitecture"),selection.get("selectedArchitecture","未選択"))
    draw.text((80,137),f"自動判定：{domain_ja} ／ {landform_ja} ／ 選択モデル：{architecture_ja}",
              font=_font(18),fill="#28506f")
    relief=model["terrainSurfaceAudit"]["surfaceReliefM"]
    draw.text((right-10,top+38),f"DEM地表比高 {relief:.2f} m / {xmax:.1f} m",
              font=_font(16),anchor="ra",fill="#52606c")
    horizontal_ticks=list(np.arange(0,xmax,spec["horizontalTickM"]))+[xmax]
    for value in horizontal_ticks:
        px,_=pt(value,zmin);draw.line((px,bottom,px,bottom+7),fill="#44515d",width=2);draw.text((px,bottom+12),f"{value:.0f}",font=_font(18),anchor="mt",fill="#263441")
    draw.text(((left+right)/2,bottom+45),"測線距離 (m)",font=_font(21),anchor="mt",fill="#263441")
    # Bilateral elevation ticks are mandatory.  The final upper/lower frame
    # values are included even when they are not multiples of the nice tick.
    vertical_ticks=list(np.arange(math.ceil(zmin/spec["verticalTickM"])*spec["verticalTickM"],
                                  zmax,spec["verticalTickM"]))
    for value in vertical_ticks:
        _,py=pt(0,value)
        draw.line((left-7,py,left,py),fill="#44515d",width=2)
        draw.line((right,py,right+7,py),fill="#44515d",width=2)
        label=f"{value:.0f}"
        draw.text((left-12,py),label,font=_font(16),anchor="rm",fill="#263441")
        draw.text((right+12,py),label,font=_font(16),anchor="lm",fill="#263441")
    draw.text((left+10,top+10),"標高 (m)",font=_font(17),fill="#52606c")
    draw.text((right-10,top+10),"標高 (m)",font=_font(17),anchor="ra",fill="#52606c")
    draw.text((left,top-22),f"{spec['leftDirection']}  {spec['sectionId'].split('–')[0]}",font=_font(18),fill="#263441")
    draw.text((right,top-22),f"{spec['sectionId'].split('–')[1]}  {spec['rightDirection']}",font=_font(18),anchor="ra",fill="#263441")
    # Synthetic body legend and mapped-surface legend are visibly separated.
    visible_ids={v["unitId"] for v in bodies if v["unitId"]==basement_id or any(v.get("activeMask",[]))}
    visible_definitions=[v for v in model["renderingLithologies"] if v["unitId"] in visible_ids]
    legend_top=830
    for i,item in enumerate(visible_definitions):
        col=i%2;row=i//2;lx=130+col*800;ly=legend_top+row*31
        draw.rectangle((lx,ly,lx+24,ly+20),fill=item["color"],outline="#555")
        draw.text((lx+34,ly-4),item["label"],font=_font(17),fill="#263441")
    lithology_rows=max(1,math.ceil(len(visible_definitions)/2))
    surface_legend_top=legend_top+lithology_rows*31+18
    horizontal_m_per_px=(xmax-xmin)/(right-left)
    vertical_m_per_px=(zmax-zmin)/(bottom-top)
    vertical_exaggeration=horizontal_m_per_px/vertical_m_per_px
    draw.text((right,surface_legend_top-2),f"水平・鉛直単位: m ／ 垂直誇張 約{vertical_exaggeration:.2f}倍",
              font=_font(16),anchor="ra",fill="#52606c")
    draw.text((130,surface_legend_top),"GSJ地表地質（地表線だけに表示）",font=_font(18),fill="#8a3b12")
    legend=[]
    for item in values:
        key=(item["symbol"],item["lithologyJa"],item["formationAgeJa"],item["color"])
        if key not in legend:legend.append(key)
    for i,(symbol,lith,age,color) in enumerate(legend[:4]):
        lx=130;ly=surface_legend_top+27+i*27
        draw.line((lx,ly+9,lx+25,ly+9),fill=color or "#d4d4d4",width=5)
        label=f"{symbol or '未区分'}：{lith or '地質図範囲外'} ({age or '年代未取得'})"
        if len(label)>92:label=label[:91]+"…"
        draw.text((lx+34,ly-3),label,font=_font(15),fill="#263441")
    # Graphic scale uses the same exact station coordinate system as the axis.
    bar_length=min(spec["horizontalTickM"],xmax)
    bx=right-360;by=surface_legend_top+42
    draw.line((bx,by,pt(bar_length,zmin)[0]-left+bx,by),fill="#263441",width=5)
    draw.line((bx,by-6,bx,by+6),fill="#263441",width=2)
    draw.line((pt(bar_length,zmin)[0]-left+bx,by-6,pt(bar_length,zmin)[0]-left+bx,by+6),fill="#263441",width=2)
    draw.text((bx,by+10),f"0      {bar_length:.0f} m",font=_font(15),fill="#263441")
    terrain_source=model.get("terrainModel",{}).get("sourceId","Unknown")
    geology_source=model.get("planGeologicalDomainClassification",{}).get("sourceId","Unknown")
    synthetic_sources=str(terrain_source).startswith("SYNTHETIC") or str(geology_source).startswith("SYNTHETIC")
    attribution=("入力地形・地表地質：合成回帰fixture（公式地域データではない）" if synthetic_sources else
      "出典：国土地理院 標高タイルを加工／産総研地質調査総合センター 20万分の1日本シームレス地質図V2を加工")
    draw.text((130,1118),attribution,font=_font(14),fill="#465663")
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True);image.save(target)
    model["renderAudit"]={"mappedSurfaceTransitionCount":len(transitions),"contactLines":contact_lines,
      "mappedSurfaceRenderedAsEvidenceLine":True,"mappedSurfaceVerticalProjectionCount":0,
      "renderedLithologyCount":len(visible_definitions),"bottomCoverageFraction":1.0,
      "subsurfaceVerticalBoundaryCount":0,"basementFilledToFrame":True,
      "eventEngineConnected":True,
      "nonConformableGeometryPresent":model["modelAudit"]["nonConformableGeometryPresent"],
      "localizedEventSuppressedByPriorGate":model["modelAudit"]["localizedEventSuppressedByPriorGate"],
      "verticalExaggeration":float(vertical_exaggeration),
      "legendLayout":"DynamicFromVisibleLithologyCount",
      "lithologyContactDrawOrder":"Foremost_AfterTerrainAndMappedSurface",
      "draftingStandardGatePassed":preflight["draftingAudit"]["passed"],
      "bilateralElevationTicksRendered":True,
      "actualSectionLengthM":float(xmax),
      "terrainSurfaceGatePassed":model["terrainSurfaceAudit"]["passed"],
      "geologicalDomainRendered":domain.get("geologicalDomain"),
      "selectedArchitectureRendered":selection.get("selectedArchitecture"),
      "sourceAttributionRendered":True,"sourceAttributionText":attribution,
      "terrainReliefM":float(relief),
      "preOutputCompliancePassed":preflight["passed"],
      "lithologyBoundaryLineCount":preflight["lithologyBoundaryLineCount"] if contact_lines=="Show" else 0}
    model["renderAudit"]["inactiveLegendEntriesRemoved"]=len(model["renderingLithologies"])-len(visible_definitions)
    target.with_name("model.json").write_text(json.dumps(model,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    return target
