"""Evidence-constrained arbitrary-route lithology-section workflow."""
from __future__ import annotations

import math
from typing import Mapping, Sequence

import numpy as np

from .rbf_structural_surface import RbfStructuralSurface
from .surface_family import ConformableSurfaceFamily
from .qualitative_stratigraphic_constraints import (
    validate_qualitative_stratigraphic_constraints)


def _local_xy(longitudes, latitudes, longitude0, latitude0):
    radius = 6378137.0
    x = radius*math.cos(math.radians(latitude0))*np.radians(np.asarray(longitudes)-longitude0)
    y = radius*np.radians(np.asarray(latitudes)-latitude0)
    return np.column_stack((x,y))


class PositiveThicknessField:
    """RBF interpolation in log(thickness), guaranteeing positive values."""
    def __init__(self, samples, origin_lonlat, shape_parameter=.35, regularization=1e-8):
        if not isinstance(samples, Sequence) or len(samples) < 3:
            raise ValueError("at least three thickness observations are required")
        required={"longitude","latitude","trueThicknessM","sourceId","evidenceStatus"}
        if any(not isinstance(v,Mapping) or not required.issubset(v) for v in samples):
            raise ValueError("invalid thickness observation")
        values=np.asarray([v["trueThicknessM"] for v in samples],dtype=float)
        if not np.isfinite(values).all() or np.any(values<=0):
            raise ValueError("observed true thickness must be finite and positive")
        if any(v["evidenceStatus"] not in {"Observed","Literature","SyntheticAssumption","Interpreted"}
               or not v["sourceId"] for v in samples):
            raise ValueError("thickness evidence status and source are required")
        lon0,lat0=origin_lonlat
        xy=_local_xy([v["longitude"] for v in samples],[v["latitude"] for v in samples],lon0,lat0)
        self.model=RbfStructuralSurface(np.column_stack((xy,np.log(values))),
                                        shape_parameter,regularization)
        self.origin=(lon0,lat0)
        self.source_ids=sorted({str(v["sourceId"]) for v in samples})
        self.statuses=sorted({v["evidenceStatus"] for v in samples})

    def __call__(self,xy):
        return np.exp(self.model.evaluate(xy))


def build_evidence_constrained_section(plan_bundle: Mapping, reference_observations,
                                       units, shape_parameter=.35,
                                       regularization=1e-8,
                                       qualitative_constraints=None):
    """Build conformable section contacts from a plan bundle and typed evidence."""
    if not isinstance(plan_bundle,Mapping) or plan_bundle.get("schemaVersion") != "PlanEvidenceBundle-1.0":
        raise ValueError("a PlanEvidenceBundle-1.0 is required")
    profile=plan_bundle.get("terrainProfile")
    if not isinstance(profile,list) or len(profile)<2:
        raise ValueError("terrain profile is required")
    if any(row.get("elevationM") is None for row in profile):
        raise ValueError("terrain profile contains NoData")
    required={"longitude","latitude","elevationM","sourceId","evidenceStatus"}
    if (not isinstance(reference_observations,Sequence) or len(reference_observations)<3 or
        any(not isinstance(v,Mapping) or not required.issubset(v) for v in reference_observations)):
        raise ValueError("at least three reference-boundary observations are required")
    statuses={v["evidenceStatus"] for v in reference_observations}
    if not statuses <= {"Observed","Literature","SyntheticAssumption","Interpreted"}:
        raise ValueError("invalid reference evidence status")
    lon0=float(np.mean([row["longitude"] for row in profile]))
    lat0=float(np.mean([row["latitude"] for row in profile]))
    controls_xy=_local_xy([v["longitude"] for v in reference_observations],
                          [v["latitude"] for v in reference_observations],lon0,lat0)
    controls=np.column_stack((controls_xy,[v["elevationM"] for v in reference_observations]))
    reference=RbfStructuralSurface(controls,shape_parameter,regularization)
    if not isinstance(units,Sequence) or not units:
        raise ValueError("one or more ordered units are required")
    fields=[]; evidence=[]; ids=[]
    for unit in units:
        if not isinstance(unit,Mapping) or set(unit)!={"unitId","normalizedLithology","thicknessEvidence"}:
            raise ValueError("invalid unit declaration")
        if not unit["unitId"] or unit["unitId"] in ids or not unit["normalizedLithology"]:
            raise ValueError("unit IDs must be non-empty and unique")
        field=PositiveThicknessField(unit["thicknessEvidence"],(lon0,lat0),
                                     shape_parameter,regularization)
        ids.append(unit["unitId"])
        fields.append({"unitId":unit["unitId"],"trueThickness":field})
        evidence.append({"unitId":unit["unitId"],"normalizedLithology":unit["normalizedLithology"],
                         "sourceIds":field.source_ids,"evidenceStatuses":field.statuses})
    qualitative_audit=None
    if qualitative_constraints is not None:
        qualitative_audit=validate_qualitative_stratigraphic_constraints(
            qualitative_constraints)
        declared=sorted({unit_id for pair in qualitative_audit["orderedPairs"] for unit_id in pair})
        missing=[unit_id for unit_id in declared if unit_id not in ids]
        if missing:
            raise ValueError("qualitative stratigraphic units are absent from section units")
        if any(ids.index(older) >= ids.index(younger)
               for older,younger in qualitative_audit["orderedPairs"]):
            raise ValueError("section unit order contradicts qualitative stratigraphic evidence")
    route_xy=_local_xy([row["longitude"] for row in profile],
                       [row["latitude"] for row in profile],lon0,lat0)
    evaluated=ConformableSurfaceFamily(reference,fields).evaluate(route_xy)
    terrain=np.asarray([row["elevationM"] for row in profile],dtype=float)
    raw=evaluated["contactElevations"]
    contacts=[np.minimum(surface,terrain) for surface in raw]
    active=[contacts[i+1]>contacts[i]+1e-9 for i in range(len(units))]
    top_gap=np.maximum(terrain-contacts[-1],0.0)
    geological_statuses=statuses | {s for item in evidence for s in item["evidenceStatuses"]}
    real_authorized=(not ({"SyntheticAssumption","Interpreted"} & geological_statuses) and
                     plan_bundle.get("authorizationState")=="SubsurfaceInterpretationInputsPresent")
    return {"schemaVersion":"EvidenceConstrainedSection-1.0",
      "stationsM":[float(row["stationM"]) for row in profile],
      "terrainElevationM":terrain.tolist(),"contactElevationsM":[v.tolist() for v in contacts],
      "activeMasks":[v.tolist() for v in active],"units":evidence,
      "referenceSourceIds":sorted({str(v["sourceId"]) for v in reference_observations}),
      "minimumTrueThicknessM":evaluated["minimumTrueThickness"],
      "unconstrainedTopGapM":top_gap.tolist(),
      "maximumUnconstrainedTopGapM":float(np.max(top_gap)),
      "subsurfaceCoverageComplete":bool(np.all(top_gap<=1e-9)),
      "geometryPolicy":"SharedReferenceSurfacePlusPositiveLogThicknessFields",
      "qualitativeStratigraphicAudit":qualitative_audit,
      "interpretationStatus":"EvidenceConstrained" if real_authorized else "SyntheticHypothesis",
      "realRegionAuthorized":real_authorized,
      "validation":{"ordered":all(np.all(b>=a-1e-9) for a,b in zip(contacts[:-1],contacts[1:])),
                    "belowTerrain":all(np.all(v<=terrain+1e-9) for v in contacts),
                    "finite":all(np.isfinite(v).all() for v in contacts)}}
