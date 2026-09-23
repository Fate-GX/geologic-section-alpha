"""Non-local clearance gate for the curvature-aware synthetic channel."""
from __future__ import annotations
import numpy as np
from .channel_geometry_v2 import CurvatureAwareChannelGeometry,make_curvature_aware_spec


class ClearanceAwareChannelGeometry(CurvatureAwareChannelGeometry):
    """Cap bank width using separation from non-neighbouring centerline samples."""
    def __init__(self,spec):
        extra={"nonlocalArcSeparationM","nonlocalSafetyFactor"}
        if not isinstance(spec,dict) or not extra.issubset(spec):raise ValueError("non-local clearance policy required")
        base={k:v for k,v in spec.items() if k not in extra}
        super().__init__(base)
        separation=spec["nonlocalArcSeparationM"];safety=spec["nonlocalSafetyFactor"]
        if isinstance(separation,bool) or not isinstance(separation,(int,float)) or not np.isfinite(separation) or separation<=0:
            raise ValueError("nonlocalArcSeparationM must be positive")
        if isinstance(safety,bool) or not isinstance(safety,(int,float)) or not np.isfinite(safety) or not 0<safety<.5:
            raise ValueError("nonlocalSafetyFactor must be in (0,0.5)")
        station=np.concatenate(([0.0],np.cumsum(np.linalg.norm(np.diff(self.path,axis=0),axis=1))))
        clearance=np.full(len(self.path),np.inf)
        for i,point in enumerate(self.path):
            mask=np.abs(station-station[i])>=float(separation)
            if np.any(mask):clearance[i]=np.min(np.linalg.norm(self.path[mask]-point,axis=1))
        capped=np.minimum(self.local_widths,float(safety)*clearance)
        minimum=self.minimum_half_width_fraction*self.half_width
        if np.any(capped<minimum):
            bad=np.flatnonzero(capped<minimum)
            raise ValueError(f"ChannelClearanceBelowMinimum at {bad.tolist()}")
        self.local_widths=capped
        self.nonlocal_clearance=clearance;self.nonlocal_clearance.flags.writeable=False
        self.nonlocal_arc_separation=float(separation);self.nonlocal_safety_factor=float(safety)
        self.clearance_reduction_iterations=0
        audit=self.bank_audit()
        while not audit["passed"] and self.clearance_reduction_iterations<24:
            reduced=np.maximum(minimum,self.local_widths*.9)
            if np.array_equal(reduced,self.local_widths):break
            self.local_widths=reduced;self.clearance_reduction_iterations+=1
            audit=self.bank_audit()
        if not audit["passed"]:raise ValueError("ChannelBankSelfIntersectionAfterClearance")
        self.local_widths.flags.writeable=False

    def clearance_audit(self):
        bank=self.bank_audit()
        return {**bank,"nonlocalArcSeparationM":self.nonlocal_arc_separation,
                "nonlocalSafetyFactor":self.nonlocal_safety_factor,
                "clearanceReductionIterations":self.clearance_reduction_iterations,
                "minimumNonlocalCenterlineClearance":float(np.min(self.nonlocal_clearance)),
                "validationLayer":"NonlocalPolylineClearance_NotFluvialProcessModel"}


def make_clearance_aware_spec(seed=3701):
    spec=make_curvature_aware_spec(seed)
    # The original 60 m half-width cannot satisfy the topology gate on this
    # synthetic path without collapsing below its declared minimum. The v3
    # fixture therefore declares a narrower 25 m channel before construction.
    spec.update(halfWidth=25.0,nonlocalArcSeparationM=180.0,nonlocalSafetyFactor=.42)
    return spec
