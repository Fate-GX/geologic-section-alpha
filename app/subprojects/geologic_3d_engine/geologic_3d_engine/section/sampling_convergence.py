"""Sampling-convergence audit for straight vertical-section traces."""
from __future__ import annotations
import numpy as np


def audit_section_sampling(surface_evaluator,surface_ids,start_xy,end_xy,sample_counts,maximum_deviation_m):
    start=np.asarray(start_xy,dtype=float);end=np.asarray(end_xy,dtype=float)
    if start.shape!=(2,) or end.shape!=(2,) or not np.isfinite([*start,*end]).all() or np.array_equal(start,end):
        raise ValueError("finite non-zero section trace required")
    if not callable(surface_evaluator) or not surface_ids or len(set(surface_ids))!=len(surface_ids):raise ValueError("evaluator and unique surfaces required")
    if (not isinstance(sample_counts,(list,tuple)) or len(sample_counts)<2
            or any(type(n) is not int or n<3 for n in sample_counts)
            or any(b<=a for a,b in zip(sample_counts,sample_counts[1:]))):
        raise ValueError("strictly increasing sample counts >=3 required")
    if isinstance(maximum_deviation_m,bool) or not isinstance(maximum_deviation_m,(int,float)) or not np.isfinite(maximum_deviation_m) or maximum_deviation_m<=0:
        raise ValueError("positive deviation tolerance required")
    finest_n=sample_counts[-1];finest_t=np.linspace(0,1,finest_n)
    finest_xy=start+(end-start)*finest_t[:,None]
    finest={sid:np.asarray(surface_evaluator(sid,finest_xy),dtype=float) for sid in surface_ids}
    if any(v.shape!=(finest_n,) or not np.isfinite(v).all() for v in finest.values()):raise ValueError("invalid surface evaluation")
    records=[]
    for n in sample_counts[:-1]:
        t=np.linspace(0,1,n);xy=start+(end-start)*t[:,None]
        per_surface={};maximum=0.0
        for sid in surface_ids:
            coarse=np.asarray(surface_evaluator(sid,xy),dtype=float)
            if coarse.shape!=(n,) or not np.isfinite(coarse).all():raise ValueError("invalid surface evaluation")
            deviation=float(np.max(np.abs(np.interp(finest_t,t,coarse)-finest[sid])))
            per_surface[sid]=deviation;maximum=max(maximum,deviation)
        records.append({"sampleCount":n,"maximumDeviationM":maximum,"surfaceDeviationM":per_surface})
    final=records[-1]["maximumDeviationM"]
    return {"passed":bool(final<=maximum_deviation_m),"records":records,"referenceSampleCount":finest_n,
            "finalMaximumDeviationM":final,"maximumDeviationM":float(maximum_deviation_m),
            "validationLayer":"SectionSamplingConvergence_NotGeologicalTruth"}
