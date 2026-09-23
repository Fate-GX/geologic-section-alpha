"""Auditable horizontal and vertical coordinate alignment for evidence."""
from __future__ import annotations

import math
from typing import Callable, Mapping, Sequence


def ellipsoidal_to_orthometric_height(ellipsoidal_height_m, geoid_height_m,
                                      reference_surface_correction_m=0.0):
    """GSI 2024 convention: H = h - N - C (C is island correction)."""
    values=(ellipsoidal_height_m,geoid_height_m,reference_surface_correction_m)
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)
           for v in values):
        raise ValueError("height, geoid and correction must be finite numbers")
    return float(ellipsoidal_height_m-geoid_height_m-reference_surface_correction_m)


def align_observations(records: Sequence[Mapping], transform_xy: Callable,
                       inverse_xy: Callable, target_crs: str,
                       target_vertical_datum: str, maximum_roundtrip_error_m: float,
                       target_axis_order="EastingNorthing"):
    """Transform evidence while retaining source coordinates and audit residuals."""
    if (not callable(transform_xy) or not callable(inverse_xy) or not target_crs or
        not target_vertical_datum or target_axis_order not in {"EastingNorthing","NorthingEasting"} or
        isinstance(maximum_roundtrip_error_m,bool) or
        not isinstance(maximum_roundtrip_error_m,(int,float)) or
        maximum_roundtrip_error_m<0 or not math.isfinite(maximum_roundtrip_error_m)):
        raise ValueError("transformers, target systems and residual limit are required")
    output=[]; errors=[]
    required={"observationId","longitude","latitude","heightM","heightType",
              "horizontalCrs","verticalDatum","coordinateEpoch","sourceId"}
    for record in records:
        if not isinstance(record,Mapping) or not required.issubset(record):
            raise ValueError("coordinate evidence is incomplete")
        nums=(record["longitude"],record["latitude"],record["heightM"])
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in nums):
            raise ValueError("source coordinates and height must be finite")
        if not all(record[k] for k in ("observationId","horizontalCrs","verticalDatum",
                                       "coordinateEpoch","sourceId")):
            raise ValueError("coordinate identity, systems, epoch and source are required")
        if record["heightType"]=="Orthometric":
            if record["verticalDatum"]!=target_vertical_datum:
                errors.append({"code":"VerticalDatumTransformationRequired",
                               "observationId":record["observationId"]})
                continue
            height=float(record["heightM"]); vertical_method="IdentitySameDatum"
        elif record["heightType"]=="Ellipsoidal":
            if not {"geoidHeightM","geoidModel","referenceSurfaceCorrectionM"}.issubset(record):
                errors.append({"code":"GeoidEvidenceRequired","observationId":record["observationId"]})
                continue
            height=ellipsoidal_to_orthometric_height(record["heightM"],record["geoidHeightM"],
                                                     record["referenceSurfaceCorrectionM"])
            vertical_method=f"{record['geoidModel']}:H=h-N-C"
        else:
            raise ValueError("heightType must be Orthometric or Ellipsoidal")
        x,y=map(float,transform_xy(record["longitude"],record["latitude"],
                                   record["horizontalCrs"],target_crs,record["coordinateEpoch"]))
        lon,lat=map(float,inverse_xy(x,y,target_crs,record["horizontalCrs"],record["coordinateEpoch"]))
        # Convert angular round-trip residual to a conservative local metric.
        dx=6378137*math.cos(math.radians(record["latitude"]))*math.radians(lon-record["longitude"])
        dy=6378137*math.radians(lat-record["latitude"])
        residual=math.hypot(dx,dy)
        item={"observationId":record["observationId"],"sourceId":record["sourceId"],
              "sourceLonLat":[float(record["longitude"]),float(record["latitude"])],
              "sourceHorizontalCrs":record["horizontalCrs"],"coordinateEpoch":record["coordinateEpoch"],
              "targetXY":[x,y],"targetCrs":target_crs,"orthometricHeightM":height,
              "targetAxisOrder":target_axis_order,
              "targetVerticalDatum":target_vertical_datum,"verticalTransform":vertical_method,
              "horizontalRoundtripErrorM":residual}
        output.append(item)
        if not math.isfinite(residual) or residual>maximum_roundtrip_error_m:
            errors.append({"code":"HorizontalRoundtripResidualExceeded",**item})
    return {"passed":not errors,"records":output,"errors":errors,
            "targetCrs":target_crs,"targetVerticalDatum":target_vertical_datum,
            "validationBoundary":"CoordinateAlignment_NotObservationAccuracy"}
