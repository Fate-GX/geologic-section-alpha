"""Evidence-labelled vertical-throw comparator for a mapped planar fault trace."""
from __future__ import annotations

import numpy as np


class VerticalThrowFault:
    def __init__(self,fault_id,trace_start_xy,trace_end_xy,downthrown_side,throw_m,source_id):
        start=np.asarray(trace_start_xy,dtype=float);end=np.asarray(trace_end_xy,dtype=float)
        if start.shape!=(2,) or end.shape!=(2,) or not np.isfinite([*start,*end]).all() or np.array_equal(start,end):
            raise ValueError("finite non-zero fault trace required")
        if downthrown_side not in ("Left","Right") or isinstance(throw_m,bool) or not isinstance(throw_m,(int,float)) or not np.isfinite(throw_m) or throw_m<=0:
            raise ValueError("side and positive throw required")
        if not fault_id or not source_id: raise ValueError("fault and source identity required")
        self.fault_id=str(fault_id);self.start=start;self.vector=end-start
        self.side=downthrown_side;self.throw=float(throw_m);self.source_id=str(source_id)

    def signed_side(self,xy):
        points=np.asarray(xy,dtype=float)
        if points.ndim!=2 or points.shape[1]!=2 or not np.isfinite(points).all():raise ValueError("finite N x 2 query required")
        delta=points-self.start
        return self.vector[0]*delta[:,1]-self.vector[1]*delta[:,0]

    def displacement(self,xy):
        side=self.signed_side(xy)
        selected=side>0 if self.side=="Left" else side<0
        return np.where(selected,-self.throw,0.0)

    def apply(self,elevations,xy):
        values=np.asarray(elevations,dtype=float)
        shift=self.displacement(xy)
        if values.shape!=shift.shape:raise ValueError("one elevation per XY query required")
        return values+shift

    def evidence(self):
        return {"faultId":self.fault_id,"sourceId":self.source_id,"throwM":self.throw,
          "downthrownSide":self.side,"kinematicScope":"VerticalThrowComparator_NotGeneralSlip"}
