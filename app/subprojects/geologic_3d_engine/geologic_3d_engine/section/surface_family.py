"""Shared structural surface family with explicit local true-thickness policy."""
from __future__ import annotations

import numpy as np


class ConformableSurfaceFamily:
    def __init__(self, reference_surface, thickness_fields):
        if not hasattr(reference_surface,"evaluate") or not hasattr(reference_surface,"gradient"):
            raise ValueError("reference surface must provide evaluate and gradient")
        if not isinstance(thickness_fields,list) or not thickness_fields:
            raise ValueError("one or more thickness fields are required")
        normalized=[]
        for index,field in enumerate(thickness_fields):
            if not isinstance(field,dict) or set(field)!={"unitId","trueThickness"}:
                raise ValueError("thickness field requires unitId and trueThickness")
            if not field["unitId"] or not callable(field["trueThickness"]):
                raise ValueError("invalid thickness field")
            normalized.append((str(field["unitId"]),field["trueThickness"]))
        self.reference=reference_surface; self.fields=normalized

    def evaluate(self,query_xy):
        xy=np.asarray(query_xy,dtype=float)
        base=self.reference.evaluate(xy)
        gradient=self.reference.gradient(xy)
        normal_to_vertical=np.sqrt(1+np.sum(gradient*gradient,axis=1))
        contacts=[base.copy()]; thicknesses=[]
        current=base.copy()
        for unit_id,field in self.fields:
            true=np.asarray(field(xy),dtype=float)
            if true.shape!=(len(xy),) or not np.isfinite(true).all() or np.any(true<=0):
                raise ValueError("true thickness must be finite, positive and one value per query")
            vertical=true*normal_to_vertical
            current=current+vertical
            contacts.append(current.copy())
            thicknesses.append({"unitId":unit_id,"trueThickness":true,
                                "verticalThickness":vertical})
        return {"contactElevations":contacts,"units":thicknesses,
                "thicknessPolicy":"LocalPlanarNormalThicknessApproximation",
                "minimumTrueThickness":float(min(np.min(v["trueThickness"]) for v in thicknesses))}


def truncate_by_unconformity(contact_elevations, unconformity_elevation):
    unconformity=np.asarray(unconformity_elevation,dtype=float)
    contacts=[np.asarray(v,dtype=float) for v in contact_elevations]
    if not contacts or any(v.shape!=unconformity.shape for v in contacts):
        raise ValueError("contacts and unconformity must share shape")
    clipped=[np.minimum(v,unconformity) for v in contacts]
    active=[clipped[i+1]>clipped[i] for i in range(len(clipped)-1)]
    return {"contactElevations":clipped,"activeMasks":active,
            "eventType":"Unconformity","geometryPolicy":"OlderUnitsTruncatedAtSurface"}
