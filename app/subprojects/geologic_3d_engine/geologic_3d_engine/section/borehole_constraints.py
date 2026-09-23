"""Borehole boundary evidence and round-trip validation for section models."""
from __future__ import annotations

import numpy as np


def validate_borehole_boundaries(boreholes, surface_evaluator, maximum_residual):
    if (not callable(surface_evaluator) or isinstance(maximum_residual,bool)
            or not isinstance(maximum_residual,(int,float))
            or not np.isfinite(maximum_residual) or maximum_residual < 0):
        raise ValueError("surface evaluator and non-negative residual limit required")
    records=[]; errors=[]
    for hole in boreholes:
        required={"boreholeId","xy","collarElevation","verticalDatum","sourceId","boundaries"}
        if not isinstance(hole,dict) or set(hole)!=required:
            raise ValueError("invalid borehole record")
        xy=np.asarray(hole["xy"],dtype=float)
        if xy.shape!=(2,) or not np.isfinite(xy).all() or not hole["boreholeId"] or not hole["sourceId"]:
            raise ValueError("invalid borehole identity or location")
        if isinstance(hole["collarElevation"],bool) or not isinstance(hole["collarElevation"],(int,float)):
            raise ValueError("finite collar and vertical datum required")
        collar=float(hole["collarElevation"])
        if not np.isfinite(collar) or not hole["verticalDatum"]:
            raise ValueError("finite collar and vertical datum required")
        seen=set()
        for boundary in hole["boundaries"]:
            if not isinstance(boundary,dict) or set(boundary)!={"surfaceId","depth","evidenceKind"}:
                raise ValueError("invalid borehole boundary")
            if isinstance(boundary["depth"],bool) or not isinstance(boundary["depth"],(int,float)):
                raise ValueError("duplicate surface or invalid depth")
            surface_id=boundary["surfaceId"]; depth=float(boundary["depth"])
            if surface_id in seen or not surface_id or not np.isfinite(depth) or depth<0:
                raise ValueError("duplicate surface or invalid depth")
            seen.add(surface_id)
            observed=collar-depth
            predicted=float(surface_evaluator(surface_id,xy[None,:])[0])
            residual=predicted-observed
            record={"boreholeId":hole["boreholeId"],"surfaceId":surface_id,
              "sourceId":hole["sourceId"],"sourceXY":xy.tolist(),"observedElevation":observed,
              "predictedElevation":predicted,"residual":residual,
              "absoluteResidual":abs(residual),"evidenceKind":boundary["evidenceKind"]}
            records.append(record)
            if abs(residual)>maximum_residual:
                errors.append({"code":"BoreholeBoundaryResidualExceeded",**record})
    return {"passed":not errors,"boundaryCount":len(records),"records":records,"errors":errors,
      "maximumAbsoluteResidual":max((r["absoluteResidual"] for r in records),default=0.0),
      "validationLayer":"ObservedBoundaryRoundTrip_NotGeologicalTruth"}
