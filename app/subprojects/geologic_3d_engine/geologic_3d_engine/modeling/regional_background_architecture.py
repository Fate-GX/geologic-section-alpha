"""Regional background-contact architectures independent of modern terrain shape."""
from __future__ import annotations

import math
import numpy as np
from .artifact_hash import signed_artifact


def apply_volcanic_paleosurface_stack(composition, *, seed, dip_degrees=-8.0):
    """Replace terrain-offset contacts by non-crossing synthetic paleosurfaces.

    Modern terrain is used only as the upper truncation envelope.  Independent
    dipping paleosurfaces determine deeper contacts.
    """
    stations=np.asarray(composition["stationsM"],float)
    terrain=np.asarray(composition["terrainElevationM"],float)
    if stations.size<5 or not np.isfinite(stations).all() or not np.isfinite(terrain).all():
        raise ValueError("finite terrain and at least five stations are required")
    rng=np.random.default_rng(int(seed)+73001)
    original=composition["layersTopDown"];layers=[];top=terrain.copy();cumulative=0.0
    centered=stations-stations.mean();span=float(np.ptp(stations))
    for index,source in enumerate(original):
        mean=float(np.mean(source["thicknessM"]));cumulative+=mean
        if index==0:
            thickness=np.clip(np.asarray(source["thicknessM"],float),.15,5.0)
            bottom=top-thickness
        elif index==len(original)-1:
            thickness=np.maximum(np.asarray(source["thicknessM"],float),1.0)
            bottom=top-thickness
        else:
            local_dip=math.radians(float(dip_degrees)+float(rng.uniform(-1.8,1.8)))
            phase=float(rng.uniform(0,2*math.pi));phase2=float(rng.uniform(0,2*math.pi))
            wavelength=max(span*float(rng.uniform(.45,.9)),1.0)
            relief=(.18*mean*np.sin(2*math.pi*stations/wavelength+phase)+
                    .07*mean*np.sin(4*math.pi*stations/wavelength+phase2))
            reference=float(np.mean(terrain))-cumulative+math.tan(local_dip)*centered+relief
            bottom=np.minimum(top,reference)
            thickness=top-bottom
        layers.append({**{k:v for k,v in source.items() if k not in
                           {"topElevationM","bottomElevationM","thicknessM"}},
                       "topElevationM":top.tolist(),"bottomElevationM":bottom.tolist(),
                       "thicknessM":thickness.tolist(),
                       "allowPinchout":index not in {0,len(original)-1},
                       "activeMask":[bool(v>1e-9) for v in thickness]})
        top=bottom
    return signed_artifact({**{k:v for k,v in composition.items() if k not in
                               {"artifactSha256","layersTopDown","compositionMethod"}},
      "layersTopDown":layers,
      "compositionMethod":"ModernTerrainTruncatesIndependentVolcanicPaleosurfaceStack",
      "backgroundArchitecture":{"type":"VolcanicPaleosurfaceStack","seed":int(seed),
        "modernTerrainRole":"UpperTruncationEnvelopeOnly","dipDegrees":float(dip_degrees),
        "basisType":"SyntheticAssumption","surfaceCoverMaximumM":5.0,
        "weatheringRepresentation":"ParentRockState_NotSeparateThickBody"}})

def _replace_with_shared_surfaces(composition,bottoms,architecture):
    original=composition["layersTopDown"];layers=[]
    top=np.asarray(composition["terrainElevationM"],float)
    for index,(source,bottom) in enumerate(zip(original,bottoms)):
        bottom=np.minimum(top,np.asarray(bottom,float));thickness=top-bottom
        layers.append({**{k:v for k,v in source.items() if k not in {"topElevationM","bottomElevationM","thicknessM"}},
          "topElevationM":top.tolist(),"bottomElevationM":bottom.tolist(),"thicknessM":thickness.tolist(),
          "allowPinchout":index not in {0,len(original)-1},"activeMask":[bool(v>1e-9) for v in thickness]})
        top=bottom
    return signed_artifact({**{k:v for k,v in composition.items() if k not in {"artifactSha256","layersTopDown","compositionMethod"}},
      "layersTopDown":layers,"compositionMethod":architecture["compositionMethod"],"backgroundArchitecture":architecture})

def apply_deformed_sedimentary_stack(composition,*,seed,dip_degrees=2.0):
    """Create shared, gently folded contacts independent of modern terrain."""
    x=np.asarray(composition["stationsM"],float);terrain=np.asarray(composition["terrainElevationM"],float)
    if x.size<5 or np.ptp(x)<=0:raise ValueError("finite nonzero section span required")
    rng=np.random.default_rng(int(seed)+73103);span=float(np.ptp(x));center=x.mean()
    means=[float(np.mean(row["thicknessM"])) for row in composition["layersTopDown"]]
    bottoms=[];reference=float(np.mean(terrain));cumulative=0.0
    for index,mean in enumerate(means):
        cumulative+=mean
        if index==0:bottoms.append(terrain-np.clip(composition["layersTopDown"][0]["thicknessM"],.15,4.0));continue
        if index==len(means)-1:bottoms.append(np.asarray(bottoms[-1])-np.maximum(composition["layersTopDown"][index]["thicknessM"],1.0));continue
        wavelength=span*rng.uniform(.8,1.45);phase=rng.uniform(0,2*math.pi)
        fold=(.12*mean+.012*cumulative)*np.sin(2*math.pi*x/wavelength+phase)
        dip=math.tan(math.radians(dip_degrees+rng.uniform(-2,2)))*(x-center)
        bottoms.append(reference-cumulative+dip+fold)
    return _replace_with_shared_surfaces(composition,bottoms,{"type":"DeformedSedimentaryStack","seed":int(seed),
      "compositionMethod":"IndependentDepositionalContactsWithSharedFoldField","modernTerrainRole":"UpperTruncationEnvelopeOnly",
      "dipDegrees":float(dip_degrees),"basisType":"SyntheticAssumption","surfaceCoverMaximumM":4.0,
      "weatheringRepresentation":"ParentRockState_NotSeparateThickBody"})

def apply_plutonic_weathering_mass(composition,*,seed):
    """Represent a pluton by irregular weathering-state fronts, not bedding."""
    x=np.asarray(composition["stationsM"],float);terrain=np.asarray(composition["terrainElevationM"],float)
    if x.size<5 or np.ptp(x)<=0:raise ValueError("finite nonzero section span required")
    rng=np.random.default_rng(int(seed)+73171);span=float(np.ptp(x));top=terrain.copy();bottoms=[]
    means=[float(np.mean(row["thicknessM"])) for row in composition["layersTopDown"]]
    for index,mean in enumerate(means):
        if index==0:thickness=np.clip(composition["layersTopDown"][0]["thicknessM"],.1,3.0)
        elif index==len(means)-1:thickness=np.maximum(composition["layersTopDown"][index]["thicknessM"],1.0)
        else:
            phase=rng.uniform(0,2*math.pi);wavelength=span*rng.uniform(.28,.75)
            thickness=np.maximum(.15,mean*(1+.28*np.sin(2*math.pi*x/wavelength+phase)))
        bottom=top-thickness;bottoms.append(bottom);top=bottom
    return _replace_with_shared_surfaces(composition,bottoms,{"type":"PlutonicWeatheringMass","seed":int(seed),
      "compositionMethod":"IrregularWeatheringStateFrontsWithinPlutonicMass",
      "modernTerrainRole":"UpperBoundaryAndWeatheringDriver_NotBeddingTemplate","basisType":"SyntheticAssumption",
      "surfaceCoverMaximumM":3.0,"weatheringRepresentation":"GradedParentRockState_NotStratigraphicBeds"})
