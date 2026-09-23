"""Classify whether a raster artifact can supply numeric section evidence."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence


def assess_numeric_raster_evidence(metadata: Mapping):
    required={"width","height","bands","crs","geotransform","quantity","unit"}
    if not isinstance(metadata,Mapping) or not required.issubset(metadata):
        raise ValueError("raster metadata is incomplete")
    if (isinstance(metadata["width"],bool) or isinstance(metadata["height"],bool) or
            not isinstance(metadata["width"],int) or not isinstance(metadata["height"],int) or
            metadata["width"]<=0 or metadata["height"]<=0):
        raise ValueError("raster dimensions must be positive integers")
    bands=metadata["bands"]
    if not isinstance(bands,Sequence) or not bands or any(not isinstance(v,Mapping) for v in bands):
        raise ValueError("raster bands are required")
    reasons=[]
    if not isinstance(metadata["crs"],str) or not metadata["crs"].strip():
        reasons.append("MissingCoordinateReferenceSystem")
    transform=metadata["geotransform"]
    if not isinstance(transform,Sequence) or len(transform)!=6:
        reasons.append("MissingOrInvalidGeotransform")
    if len(bands)!=1:
        reasons.append("NotSingleNumericQuantityBand")
    color_interpretations={str(v.get("colorInterpretation","")) for v in bands}
    if color_interpretations & {"Red","Green","Blue","Palette"}:
        reasons.append("RenderedColorImage_NotNumericQuantity")
    if any(str(v.get("dataType","")) not in {"Int16","UInt16","Int32","UInt32","Float32","Float64"}
           for v in bands):
        reasons.append("UnsupportedOrDisplayOnlyBandType")
    if not isinstance(metadata["quantity"],str) or not metadata["quantity"].strip():
        reasons.append("QuantityUndefined")
    if not isinstance(metadata["unit"],str) or not metadata["unit"].strip():
        reasons.append("UnitUndefined")
    usable=not reasons
    payload={"schemaVersion":"NumericRasterEvidenceAssessment-1.0",
      "width":metadata["width"],"height":metadata["height"],"bandCount":len(bands),
      "numericSamplingAuthorized":usable,
      "classification":"NumericGeoreferencedRaster" if usable else "IllustrationOnly_NotNumericRaster",
      "blockingReasons":reasons,
      "boundary":"RasterContainerOrFilenameDoesNotEstablishNumericEvidence"}
    payload["recordSha256"]=hashlib.sha256(json.dumps(payload,sort_keys=True,
      separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()
    return payload
