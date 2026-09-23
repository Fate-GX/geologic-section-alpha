"""Adapt a terrain-independent conformable section to the shared event engine.

The event geometry is an explicitly synthetic demonstration.  Mapped surface
geology is deliberately not accepted by this module.
"""
from __future__ import annotations
import numpy as np
from ..geometry.regular_grid import RegularGrid3D
from ..stratigraphy.conformable_stack import ConformableStack,LayerVolume
from ..events.stratigraphic_events import (from_conformable_stack,apply_erosion,
  build_stratified_erosion_fill)
from ..modeling.lithology_section_model import generate_basic_relative_depth_lithology
from ..fields.separable_gaussian import sample_separable_gaussian,machine_eigen_tolerance

def _rows(values):
    return (tuple(float(v) for v in values),)

def _active_top(model):
    """Return the material top at every section station."""
    return np.asarray([[max((body.top[0][x] for body in model.primary_bodies
                              if body.active[0][x]),
                             default=model.grid.minimum[2])
                        for x in range(model.grid.nx)]],float)

def _smooth_compact_support(value):
    value=np.asarray(value,float)
    return np.where(abs(value)<1.0,(1.0-value*value)**2,0.0)

def build_multiscale_synthetic_erosion_depth(stations_m,*,seed):
    """Return a terrain-independent, finite-support synthetic incision depth."""
    stations=np.asarray(stations_m,float)
    if stations.ndim!=1 or len(stations)<5 or stations[0]!=0 or not np.isfinite(stations).all() or np.any(np.diff(stations)<=0):
        raise ValueError("ordered finite stations beginning at zero are required")
    spacing=np.diff(stations)
    if not np.allclose(spacing,spacing[0],rtol=0,atol=1e-8):
        raise ValueError("erosion-depth generator requires regular stations")
    if not isinstance(seed,int) or isinstance(seed,bool):raise ValueError("integer seed required")
    length=float(stations[-1]);u=stations/max(length,1.0)
    rng=np.random.default_rng(seed+4109)
    # Seeded geometry remains inside conservative interior bounds. Left and
    # right half-widths differ deliberately; neither depends on terrain.
    center=.46+rng.uniform(-.05,.05)
    left_width=.28+rng.uniform(-.025,.025)
    right_width=.36+rng.uniform(-.025,.025)
    q=np.where(u<center,(center-u)/left_width,(u-center)/right_width)
    support=np.where(q<1.0,(1.0-q*q)**2,0.0)
    def field(range_m):
        return sample_separable_gaussian(nx=len(stations),ny=1,
          spacing_x=float(spacing[0]),spacing_y=1.0,range_x=float(range_m),range_y=1.0,
          variance=1.0,standard_normal=rng.standard_normal((1,len(stations))),
          negative_eigen_tolerances=(machine_eigen_tolerance(len(stations)),
                                     machine_eigen_tolerance(1)))[0]
    low=field(max(length*.24,float(spacing[0])*3.0))
    high=field(max(length*.065,float(spacing[0])*1.5))
    modulation=np.clip(1.0+.20*low+.07*high,.45,1.55)
    skew=np.clip(1.0+.22*(u-center)/max(left_width,right_width),.72,1.28)
    # Valley shoulders, thalweg and terrace are separate geometric controls.
    # This avoids the mirror-symmetric bowl produced when the deepest point is
    # forced to coincide with the footprint centre.
    thalweg_center=float(np.clip(center+rng.uniform(.055,.12),center+.03,
                                center+right_width*.68))
    thalweg_width=.055+rng.uniform(0,.025)
    thalweg=_smooth_compact_support((u-thalweg_center)/thalweg_width)
    terrace_center=float(np.clip(center-left_width*(.58+rng.uniform(-.08,.08)),
                                center-left_width*.78,center-left_width*.34))
    terrace_width=.055+rng.uniform(0,.018)
    terrace=_smooth_compact_support((u-terrace_center)/terrace_width)
    depth=58.0*support*modulation*skew+8.5*thalweg*support-3.8*terrace*support
    depth=np.maximum(depth,0.0)
    depth[support==0.0]=0.0
    active=depth>1e-9
    transitions=int(np.count_nonzero(active[1:]!=active[:-1]))
    if transitions!=2:raise ValueError("synthetic erosion footprint must be one finite interval")
    gradient=np.diff(depth)/spacing
    return {"depthM":depth.tolist(),"activeMask":active.tolist(),
      "parameters":{"centerFraction":float(center),"leftWidthFraction":float(left_width),
        "rightWidthFraction":float(right_width),"maximumNominalDepthM":58.0,
        "thalwegCenterFraction":thalweg_center,"thalwegWidthFraction":float(thalweg_width),
        "terraceCenterFraction":terrace_center,"terraceWidthFraction":float(terrace_width),
        "lowFrequencyRangeM":max(length*.24,float(spacing[0])*3.0),
        "highFrequencyRangeM":max(length*.065,float(spacing[0])*1.5)},
      "audit":{"finiteSupport":True,"activeTransitionCount":transitions,
        "inactiveStationCount":int((~active).sum()),"maximumAbsoluteGradient":float(np.max(abs(gradient))),
        "asymmetricWidths":bool(abs(left_width-right_width)>1e-9),
        "shoulderAndThalwegSeparated":bool(abs(thalweg_center-center)>.03),
        "terrainInputAccepted":False},"basisType":"SyntheticAssumption",
      "geologicalValidity":"NotAssessed","realRegionAuthorized":False}

def apply_synthetic_event_architecture(composition,stations_m,*,seed,regional_profile=None):
    """Run erosion and a synthetic, internally stratified valley fill."""
    stations=np.asarray(stations_m,float)
    source=composition["layersTopDown"]
    if len(source)<5:raise ValueError("event adapter requires at least five older units")
    dx=float(np.median(np.diff(stations)))
    minimum=min(min(v["bottomElevationM"]) for v in source)-100.0
    maximum=max(composition["terrainElevationM"])+100.0
    grid=RegularGrid3D((0.0,0.0,minimum),(dx*len(stations),1.0,maximum),(dx,1.0,maximum-minimum),(1,1,len(stations)))
    layers=[]
    for index,item in enumerate(source):
        thickness=np.asarray(item["thicknessM"],float)
        layers.append(LayerVolume(item["unitId"],index,_rows(item["topElevationM"]),
          _rows(item["bottomElevationM"]),_rows(thickness),
          (tuple(bool(v>1e-9) for v in thickness),)))
    stack=ConformableStack(grid,tuple(layers),1e-9)
    report=stack.validate()
    if not report["passed"]:raise ValueError("source stack failed event-adapter validation")

    terrain=np.asarray(composition["terrainElevationM"],float)
    length=max(float(stations[-1]),1.0)
    erosion_definition=build_multiscale_synthetic_erosion_depth(stations,seed=seed)
    erosion_depth=np.asarray(erosion_definition["depthM"],float)
    erosion_surface=terrain-erosion_depth
    eroded=apply_erosion(from_conformable_stack(stack),[erosion_surface.tolist()],
      "SYN-EROSION-1")
    effective=np.asarray(eroded.erosion_surface[0],float)
    total_fill=np.maximum(terrain-effective,0.0)
    # These are synthetic allocation weights, not a universal facies order.
    # The independent correlated fields avoid constant-offset internal contacts.
    fill_defs=(regional_profile or {}).get("fillFacies") or [
      {"unitId":"SYN-VALLEY-BASAL","label":"礫質谷底堆積物（合成）","meanWeight":.7},
      {"unitId":"SYN-VALLEY-MIXED","label":"砂泥質谷埋め堆積物（合成）","meanWeight":1.4},
      {"unitId":"SYN-VALLEY-FINE","label":"細粒谷埋め堆積物（合成）","meanWeight":1.0}]
    cap=(regional_profile or {}).get("surfaceCap")
    depositional=[v for v in fill_defs if not cap or v["unitId"]!=cap["unitId"]]
    weight_model=generate_basic_relative_depth_lithology(stations.tolist(),[
      {"unitId":v["unitId"],"normalizedLithology":v["label"],"meanThicknessM":v["meanWeight"]}
      for v in depositional],
      seed=seed+7301,range_m=max(dx*3.0,min(length*.18,420.0)),log_std=.42)
    weights=np.asarray([v["thicknessM"] for v in weight_model["layersTopDown"]],float)
    # Basal gravel is deliberately conditional and pinches out where the
    # synthetic accommodation is shallow; it is not asserted to exist regionally.
    basal_taper=np.clip((total_fill-18.0)/24.0,0.0,1.0)
    basal_taper=basal_taper*basal_taper*(3.0-2.0*basal_taper)
    if (regional_profile or {}).get("basalTaper",True):weights[0]*=basal_taper
    weights/=weights.sum(axis=0)
    cap_thickness=(np.minimum(float(cap["thicknessM"]),total_fill) if cap else np.zeros_like(total_fill))
    allocated=weights*np.maximum(total_fill-cap_thickness,0.0)
    records=[(v["unitId"],[allocated[i].tolist()],f"SYN-FILL-{i+1}")
      for i,v in enumerate(depositional)]
    if cap:records.append((cap["unitId"],[cap_thickness.tolist()],"SYN-SURFACE-CAP"))
    # A profile may opt into a real event sequence rather than allocating all
    # facies as scaled copies of one accommodation surface.  Two early units
    # are deposited first, a younger off-centre channel locally re-incises
    # them, and the remaining units fill the resulting relief.  This produces
    # genuine truncation while preserving an exclusive material partition.
    use_multievent=bool(regional_profile and len(depositional)>=4)
    if use_multievent:
      rng=np.random.default_rng(seed+11939)
      early_fraction=np.clip(.49+.07*weights[0]-.045*weights[1],.34,.64)
      early_total=np.maximum(total_fill-cap_thickness,0.0)*early_fraction
      early_weights=weights[:2].copy()
      early_weights/=np.maximum(early_weights.sum(axis=0),1e-12)
      early_records=[(depositional[i]["unitId"],[(early_total*early_weights[i]).tolist()],
                      f"SYN-EARLY-FILL-{i+1}") for i in range(2)]
      early=build_stratified_erosion_fill(eroded,early_records,
        accommodation_ceiling=[terrain.tolist()])

      # The younger channel is deliberately offset from the broad valley
      # deepest point and has unequal banks.  Its compact support prevents a
      # mathematically convenient section-wide cut.
      u=stations/length
      channel_center=float(np.clip(
        erosion_definition["parameters"]["centerFraction"]+rng.uniform(.08,.16),.28,.78))
      left=.105+rng.uniform(-.018,.018);right=.155+rng.uniform(-.02,.02)
      cq=np.where(u<channel_center,(channel_center-u)/left,(u-channel_center)/right)
      channel_support=_smooth_compact_support(cq)
      channel_depth=(7.0+rng.uniform(1.0,5.0))*channel_support
      # A one-sided terrace/notch interrupts the otherwise analytic bank.
      terrace_center=channel_center-left*(.58+rng.uniform(-.08,.08))
      terrace=_smooth_compact_support((u-terrace_center)/(.045+rng.uniform(0,.018)))
      channel_depth=np.maximum(0.0,channel_depth-terrace*(1.3+rng.uniform(0,.9)))
      before=_active_top(early)[0]
      reincision_surface=before-channel_depth
      reincised=apply_erosion(early,[reincision_surface.tolist()],"SYN-REINCISION-2")

      remaining=np.maximum(terrain-_active_top(reincised)[0],0.0)
      late_defs=depositional[2:]
      late_weights=weights[2:].copy()
      late_weights/=np.maximum(late_weights.sum(axis=0),1e-12)
      late_allocated=late_weights*np.maximum(remaining-cap_thickness,0.0)
      late_records=[(v["unitId"],[late_allocated[i].tolist()],f"SYN-LATE-FILL-{i+1}")
                    for i,v in enumerate(late_defs)]
      if cap:late_records.append((cap["unitId"],[np.minimum(cap_thickness,remaining).tolist()],
                                  "SYN-SURFACE-CAP"))
      filled=build_stratified_erosion_fill(reincised,late_records,
        accommodation_ceiling=[terrain.tolist()])
      multievent_audit={"enabled":True,"secondaryErosionEventId":"SYN-REINCISION-2",
        "channelCenterFraction":channel_center,"leftWidthFraction":float(left),
        "rightWidthFraction":float(right),"terraceCenterFraction":float(terrace_center),
        "maximumReincisionDepthM":float(channel_depth.max()),
        "truncatedEarlyUnitIds":[v["unitId"] for v in depositional[:2]]}
    else:
      filled=build_stratified_erosion_fill(eroded,records,
        accommodation_ceiling=[terrain.tolist()])
      multievent_audit={"enabled":False}

    # No generic lens is added. A lens needs depositional-setting evidence for
    # its length, thickness and taper, and must replace (not overdraw) its host.
    event_model=filled

    def body(value,role):
        return {"unitId":value.unit_id,"topElevationM":list(value.top[0]),
          "bottomElevationM":list(value.bottom[0]),"thicknessM":list(value.thickness[0]),
          "activeMask":list(value.active[0]),"bodyRole":role}
    bodies=[body(v,"PrimaryBody") for v in event_model.primary_bodies]
    return {"schemaVersion":"SyntheticSectionEventAdapter-1.1",
      "eventModel":event_model.to_dict(),"renderBodies":bodies,
      "eventLog":list(event_model.event_log),
      "genericLensPolicy":"ProhibitedWithoutScopedGeometryEvidence",
      "fillArchitecture":{"profileId":(regional_profile or {}).get("profileId","SyntheticIncisedValleyDemonstration-1.0"),
        "basisType":"SyntheticAssumption","universalSequenceClaimed":False,
        "basalGravelPolicy":"ContinuousAccommodationTaper_LiteraturePattern_NotSiteObservation",
        "stackingPolicy":("EarlyFill_OffCenterReincision_LateFill" if use_multievent else
                          "ErosionSurfaceThenExactPredecessorTop"),
        "multiEventArchitecture":multievent_audit,
        "weightFieldTerrainInputAccepted":False},
      "erosionSurfaceDefinition":erosion_definition,
      "mappedSurfaceInputAccepted":False,"geologicalValidity":"SyntheticAssumption",
      "realRegionAuthorized":False}

def apply_conservative_regional_architecture(composition,stations_m,*,prior_decision):
    """Expose only the conformable regional prior when local events lack evidence."""
    stations=np.asarray(stations_m,float)
    bodies=[]
    for item in composition["layersTopDown"]:
      thickness=np.asarray(item["thicknessM"],float)
      bodies.append({"unitId":item["unitId"],"topElevationM":list(item["topElevationM"]),
        "bottomElevationM":list(item["bottomElevationM"]),"thicknessM":list(item["thicknessM"]),
        "activeMask":[bool(v>1e-9) for v in thickness],"bodyRole":"PrimaryBody"})
    return {"schemaVersion":"SyntheticSectionEventAdapter-1.2",
      "architectureMode":"ConservativeRegionalPrior_NoLocalizedEvents",
      "eventModel":None,"renderBodies":bodies,
      "eventLog":[{"eventId":"REGIONAL-PRIOR-ONLY","eventType":"RegionalPriorNoLocalizedEvent",
        "reason":"Route-applicable subsurface evidence does not authorize a localized event"}],
      "genericLensPolicy":"ProhibitedWithoutScopedGeometryEvidence",
      "fillArchitecture":None,"erosionSurfaceDefinition":None,
      "geologicalPriorDecision":prior_decision,
      "mappedSurfaceInputAccepted":False,"geologicalValidity":"SyntheticAssumption",
      "realRegionAuthorized":False}
