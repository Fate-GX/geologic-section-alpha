"""Pre-generation audit for route terrain evidence and numerical fidelity."""
from __future__ import annotations

import math
import re
import numpy as np


def audit_route_terrain(plan: dict, stations_m, elevations_m) -> dict:
    """Check terrain before any subsurface model is calculated."""
    x=np.asarray(stations_m,float);z=np.asarray(elevations_m,float);errors=[];warnings=[]
    dem=next((item for item in plan.get("layers",[])
              if item.get("evidence_kind")=="DEM"),None)
    if not dem:errors.append("MissingDemEvidenceLayer")
    else:
      if not dem.get("source_id") or not dem.get("canonical_url"):
        errors.append("IncompleteDemProvenance")
      digest=dem.get("content_sha256","")
      if not isinstance(digest,str) or not re.fullmatch(r"[0-9a-f]{64}",digest):
        errors.append("InvalidDemEvidenceHash")
    if x.ndim!=1 or z.shape!=x.shape or len(x)<3 or not np.isfinite(x).all() or not np.isfinite(z).all():
      errors.append("InvalidTerrainProfile")
      return {"passed":False,"errors":errors,"warnings":warnings,
              "checkedBeforeSubsurfaceGeneration":True}
    spacing=np.diff(x);slopes=np.diff(z)/spacing
    relief=float(np.ptp(z));length=float(x[-1]-x[0]);unique=int(len(np.unique(z)))
    repeated=int(np.max(np.unique(z,return_counts=True)[1]))
    if np.any(spacing<=0):errors.append("NonIncreasingTerrainStations")
    if unique==1 and length>=100:
      errors.append("ExactlyFlatTerrainRequiresIndependentConfirmation")
    elif relief<.02 and length>=100:
      warnings.append("NearFlatTerrainRequiresVisualReview")
    if repeated/len(z)>.8:
      warnings.append("PossibleTerrainQuantization")
    if np.max(abs(slopes))>2.0:
      warnings.append("ExtremeTerrainSlopeRequiresSourceReview")
    classification=("ExactlyFlat" if relief==0 else "NearLevel" if relief<1.0 else
                    "LowRelief" if relief<5.0 else "ReliefPresent")
    return {"passed":not errors,"errors":errors,"warnings":warnings,
      "checkedBeforeSubsurfaceGeneration":True,"sourceId":None if not dem else dem.get("source_id"),
      "sampleCount":len(z),"uniqueElevationCount":unique,"routeLengthM":length,
      "minimumElevationM":float(z.min()),"maximumElevationM":float(z.max()),
      "surfaceReliefM":relief,"meanSlope":float(np.mean(slopes)),
      "maximumAbsoluteSlope":float(np.max(abs(slopes))),
      "maximumRepeatedElevationCount":repeated,"classification":classification,
      "verticalDatumStatus":"Unverified"}
