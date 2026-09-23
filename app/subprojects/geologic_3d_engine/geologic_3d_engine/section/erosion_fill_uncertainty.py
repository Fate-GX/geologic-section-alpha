"""Propagate shared-surface and event-depth ensembles through erosion and fill."""
from __future__ import annotations
import numpy as np


def propagate_erosion_fill_ensemble(old_contact_samples,unconformity_samples,
                                    channel_shape,depth_samples,lower_fill_fraction,
                                    cover_top_samples,terrain_samples):
    uncon=np.asarray(unconformity_samples,dtype=float)
    cover=np.asarray(cover_top_samples,dtype=float);terrain=np.asarray(terrain_samples,dtype=float)
    if uncon.ndim!=2 or uncon.shape!=cover.shape or uncon.shape!=terrain.shape or not np.isfinite(uncon).all() or not np.isfinite(cover).all() or not np.isfinite(terrain).all():
        raise ValueError("finite member-by-query event surfaces required")
    members,queries=uncon.shape
    if not isinstance(old_contact_samples,(list,tuple)) or not old_contact_samples:raise ValueError("old contact samples required")
    old=[np.asarray(value,dtype=float) for value in old_contact_samples]
    if any(value.shape!=uncon.shape or not np.isfinite(value).all() for value in old):raise ValueError("old contacts must share ensemble shape")
    shape=np.asarray(channel_shape,dtype=float);depth=np.asarray(depth_samples,dtype=float)
    if shape.shape!=(queries,) or not np.isfinite(shape).all() or np.any(shape<0) or np.any(shape>1):raise ValueError("channel shape must be in [0,1]")
    if depth.shape!=(members,) or not np.isfinite(depth).all() or np.any(depth<=0):raise ValueError("one positive depth per member required")
    if isinstance(lower_fill_fraction,bool) or not isinstance(lower_fill_fraction,(int,float)) or not np.isfinite(lower_fill_fraction) or not 0<lower_fill_fraction<1:
        raise ValueError("fill fraction must be in (0,1)")
    incision=depth[:,None]*shape[None,:];bed=uncon-incision;split=bed+float(lower_fill_fraction)*incision
    contacts=[]
    previous=np.full_like(uncon,-np.inf)
    for value in old:
        clipped=np.maximum(np.minimum(value,bed),previous);contacts.append(clipped);previous=clipped
    bed=np.maximum(bed,previous);split=np.maximum(split,bed);uncon=np.maximum(uncon,split)
    cover=np.maximum(cover,uncon);terrain=np.maximum(terrain,cover)
    surfaces=np.stack(contacts+[bed,split,uncon,cover,terrain],axis=1)
    violations=int(np.sum(np.diff(surfaces,axis=1)<-1e-12))
    conservation=float(np.max(np.abs((split-bed)+(uncon-split)-(uncon-bed))))
    return {"surfaceSamples":surfaces,"incisionSamples":incision,
            "memberCount":members,"queryCount":queries,
            "negativeOrderedIntervalCount":violations,
            "maximumFillConservationResidual":conservation,
            "outsideChannelFillMaximum":float(np.max((uncon-bed)[:,shape==0])) if np.any(shape==0) else None,
            "validationLayer":"SharedMemberEventPropagation_NotPosteriorOrGeologicalTruth"}


def surface_quantiles(propagation,quantiles=(.05,.5,.95)):
    samples=np.asarray(propagation["surfaceSamples"],dtype=float)
    q=np.asarray(quantiles,dtype=float)
    if q.ndim!=1 or len(q)==0 or not np.isfinite(q).all() or np.any(q<0) or np.any(q>1) or np.any(np.diff(q)<0):raise ValueError("ordered quantiles in [0,1] required")
    return {"quantiles":q.tolist(),"values":np.quantile(samples,q,axis=0),
            "uncertaintyMeaning":"SharedObservationAndEventSensitivity_NotPosterior"}
