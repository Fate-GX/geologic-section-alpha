"""Resolution-convergence audit for analytic channel incision and fill volume."""
from __future__ import annotations
import numpy as np


def audit_channel_volume_convergence(channel,bounds_xy,resolutions,maximum_relative_change):
    bounds=np.asarray(bounds_xy,dtype=float)
    if bounds.shape!=(2,2) or not np.isfinite(bounds).all() or np.any(bounds[1]<=bounds[0]):
        raise ValueError("finite increasing XY bounds required")
    if (isinstance(maximum_relative_change,bool) or not isinstance(maximum_relative_change,(int,float))
            or not np.isfinite(maximum_relative_change) or not 0<maximum_relative_change<1):
        raise ValueError("relative-change tolerance must be in (0,1)")
    if not hasattr(channel,"surfaces") or not hasattr(channel,"fraction"):raise ValueError("channel surface model required")
    if not isinstance(resolutions,(list,tuple)) or len(resolutions)<2:raise ValueError("at least two resolutions required")
    records=[];previous=None
    for resolution in resolutions:
        if (not isinstance(resolution,(list,tuple)) or len(resolution)!=2
                or any(type(v) is not int or v<2 for v in resolution)):
            raise ValueError("resolution must contain two integers >=2")
        nx,ny=resolution
        if nx*ny>1_000_000:raise ValueError("volume audit grid too large")
        dx=(bounds[1,0]-bounds[0,0])/nx;dy=(bounds[1,1]-bounds[0,1])/ny
        x=bounds[0,0]+(np.arange(nx)+.5)*dx;y=bounds[0,1]+(np.arange(ny)+.5)*dy
        xx,yy=np.meshgrid(x,y);q=np.column_stack((xx.ravel(),yy.ravel()))
        incision=np.asarray(channel.surfaces(q)["incision"],dtype=float)
        if incision.shape!=(nx*ny,) or not np.isfinite(incision).all() or np.any(incision<0):
            raise ValueError("invalid incision field")
        volume=float(np.sum(incision)*dx*dy)
        change=None if previous is None else abs(volume-previous)/max(abs(volume),abs(previous),np.finfo(float).tiny)
        records.append({"nx":nx,"ny":ny,"cellArea":float(dx*dy),"incisionVolume":volume,
                        "lowerFillVolume":volume*float(channel.fraction),
                        "upperFillVolume":volume*(1-float(channel.fraction)),
                        "relativeChangeFromPrevious":change})
        previous=volume
    final_change=records[-1]["relativeChangeFromPrevious"]
    conservation=max(abs(r["lowerFillVolume"]+r["upperFillVolume"]-r["incisionVolume"]) for r in records)
    return {"passed":bool(final_change<=maximum_relative_change and conservation<=1e-10*max(1,records[-1]["incisionVolume"])),
            "records":records,"maximumRelativeChange":maximum_relative_change,
            "finalRelativeChange":final_change,"maximumVolumeConservationResidual":conservation,
            "validationLayer":"NumericalVolumeConvergence_NotGeologicalTruth"}
