"""Cross-section network consistency audit against one shared 3D surface family."""
from __future__ import annotations
import numpy as np


def audit_section_intersection(surface_evaluator,surface_ids,intersection_xy,section_a_id,section_b_id,tolerance):
    xy=np.asarray(intersection_xy,dtype=float)
    if xy.shape!=(2,) or not np.isfinite(xy).all() or tolerance<0 or not section_a_id or not section_b_id:
        raise ValueError("invalid section intersection audit")
    records=[];errors=[]
    for surface_id in surface_ids:
        # Evaluate independently to expose stateful or section-dependent implementations.
        a=float(surface_evaluator(surface_id,xy[None,:],section_a_id)[0])
        b=float(surface_evaluator(surface_id,xy[None,:],section_b_id)[0])
        residual=a-b
        record={"surfaceId":surface_id,"sectionA":section_a_id,"sectionB":section_b_id,
                "intersectionXY":xy.tolist(),"elevationA":a,"elevationB":b,
                "absoluteResidual":abs(residual)}
        records.append(record)
        if abs(residual)>tolerance:errors.append({"code":"InterlockingSectionMismatch",**record})
    return {"passed":not errors,"records":records,"errors":errors,
            "maximumAbsoluteResidual":max((r["absoluteResidual"] for r in records),default=0.0)}
