"""Evidence-gated erosion and younger fill for an arbitrary section."""
import copy,math
from typing import Mapping
import numpy as np

def _controls(items,stations,name,allow_zero=False):
    if not isinstance(items,list) or len(items)<2:raise ValueError(f"{name} requires at least two controls")
    required={"stationM","valueM","sourceId","evidenceStatus"};ordered=[]
    for item in items:
        if not isinstance(item,Mapping) or set(item)!=required:raise ValueError(f"invalid {name} control")
        s,v=item["stationM"],item["valueM"]
        if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in (s,v)):raise ValueError(f"{name} controls must be finite")
        if item["evidenceStatus"] not in {"Observed","Literature"} or not item["sourceId"]:raise ValueError(f"{name} controls require observed/literature sources")
        if allow_zero and v<0:raise ValueError("fill thickness must be non-negative")
        ordered.append((float(s),float(v),str(item["sourceId"])))
    ordered.sort();positions=np.asarray([v[0] for v in ordered])
    if np.any(np.diff(positions)<=0):raise ValueError(f"{name} stations must be unique")
    if positions[0]>stations[0] or positions[-1]<stations[-1]:raise ValueError(f"{name} controls may not be extrapolated")
    return np.interp(stations,positions,[v[1] for v in ordered]),sorted({v[2] for v in ordered})

def apply_erosion_fill(section:Mapping,evidence:Mapping):
    required={"eventId","positiveErosionIndicators","erosionSurfaceControls","youngerUnit","fillThicknessControls"}
    if not isinstance(evidence,Mapping) or set(evidence)!=required:raise ValueError("erosion-fill evidence is incomplete")
    indicators=evidence["positiveErosionIndicators"]
    allowed={"positiveTruncation","erosionalSurface","basalLag","weatheringSurface"}
    if not isinstance(indicators,list) or not set(indicators)<=allowed or not indicators:raise ValueError("at least one positive erosion indicator is required")
    younger=evidence["youngerUnit"]
    if not isinstance(younger,Mapping) or set(younger)!={"unitId","normalizedLithology"} or not all(isinstance(v,str) and v for v in younger.values()):raise ValueError("younger unit is invalid")
    if younger["unitId"] in {v["unitId"] for v in section["units"]}:raise ValueError("younger unit ID must be unique")
    stations=np.asarray(section["stationsM"],float);terrain=np.asarray(section["terrainElevationM"],float)
    erosion,surface_sources=_controls(evidence["erosionSurfaceControls"],stations,"erosion surface")
    fill,fill_sources=_controls(evidence["fillThicknessControls"],stations,"fill thickness",True)
    old=[np.asarray(v,float) for v in section["contactElevationsM"]]
    clipped=[np.minimum(v,erosion) for v in old]
    active=[clipped[i+1]>clipped[i]+1e-9 for i in range(len(clipped)-1)]
    effective=[]
    for sample in range(len(stations)):
        tops=[clipped[i+1][sample] for i in range(len(active)) if active[i][sample]]
        if not tops:raise ValueError("erosion removes the entire represented older stack")
        effective.append(max(tops))
    effective=np.asarray(effective);young_top=np.minimum(effective+fill,terrain)
    if not np.allclose(clipped[-1],effective,rtol=0,atol=1e-9):
        raise ValueError("section contact stack cannot represent a detached effective fill base")
    result=copy.deepcopy(section);result["contactElevationsM"]=[v.tolist() for v in clipped]+[young_top.tolist()]
    result["activeMasks"]=[v.tolist() for v in active]+[(young_top>effective+1e-9).tolist()]
    result["units"].append({"unitId":younger["unitId"],"normalizedLithology":younger["normalizedLithology"],
      "sourceIds":fill_sources,"evidenceStatuses":["Interpreted"]})
    removed=sum(float(np.trapezoid(np.maximum(o-c,0),stations)) for o,c in zip(old[1:],clipped[1:]))
    result.setdefault("stratigraphicEvents",[]).append({"eventId":evidence["eventId"],"eventType":"ErosionFill",
      "positiveErosionIndicators":indicators,"erosionSurfaceM":erosion.tolist(),"effectiveFillBaseM":effective.tolist(),
      "surfaceSourceIds":surface_sources,"fillSourceIds":fill_sources,"removedSectionAreaM2":removed,
      "geometryPolicy":"OlderContactsTruncatedThenYoungerBaseSharesEffectiveRetainedTop",
      "authorization":"InterpretedEvent_NotUniqueSubsurfaceTruth"})
    result["realRegionAuthorized"]=False;result["interpretationStatus"]="SyntheticHypothesis"
    result["validation"]["erosionFillOrdered"]=all(np.all(b>=a-1e-9) for a,b in zip(clipped,clipped[1:]+[young_top]))
    return result
