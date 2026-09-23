"""Normalize public borehole-exchange evidence without inventing missing data."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Mapping, Sequence


def normalize_borehole(record: Mapping):
    required = {"boreholeId", "longitude", "latitude", "collarElevationM",
                "totalDepthM", "horizontalCrs", "verticalDatum", "sourceId",
                "sourceUrl", "exchangeFormatVersion", "intervals"}
    if not isinstance(record, Mapping) or not required.issubset(record):
        raise ValueError("borehole record lacks required provenance or geometry")
    numbers = {key: record[key] for key in
               ("longitude", "latitude", "collarElevationM", "totalDepthM")}
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) for v in numbers.values()):
        raise ValueError("borehole coordinates, collar and depth must be finite numbers")
    if not -180 <= record["longitude"] <= 180 or not -90 <= record["latitude"] <= 90:
        raise ValueError("borehole longitude/latitude are invalid")
    if record["totalDepthM"] <= 0:
        raise ValueError("total depth must be positive")
    text_fields = ("boreholeId", "horizontalCrs", "verticalDatum", "sourceId",
                   "sourceUrl", "exchangeFormatVersion")
    if not all(isinstance(record[k], str) and record[k].strip() for k in text_fields):
        raise ValueError("borehole identity, datum, source and format version are required")
    intervals = []
    previous_bottom = 0.0
    for index, item in enumerate(record["intervals"]):
        needed = {"topDepthM", "bottomDepthM", "sourceLabel", "normalizedLithology",
                  "termStatus", "evidenceStatus"}
        if not isinstance(item, Mapping) or not needed.issubset(item):
            raise ValueError("borehole interval is incomplete")
        top, bottom = item["topDepthM"], item["bottomDepthM"]
        if any(isinstance(v, bool) or not isinstance(v, (int,float)) or
               not math.isfinite(v) for v in (top,bottom)):
            raise ValueError("interval depths must be finite numbers")
        if top != previous_bottom or not top < bottom or bottom > record["totalDepthM"]:
            raise ValueError("intervals must be contiguous, ordered and inside total depth")
        if item["evidenceStatus"] not in {"Observed", "Literature", "Unverified"}:
            raise ValueError("invalid borehole evidence status")
        if item["termStatus"] not in {"Current", "Legacy", "Unverified"}:
            raise ValueError("invalid terminology status")
        intervals.append({**dict(item),
            "topElevationM":float(record["collarElevationM"]-top),
            "bottomElevationM":float(record["collarElevationM"]-bottom),
            "intervalIndex":index})
        previous_bottom = float(bottom)
    if not intervals:
        raise ValueError("at least one borehole interval is required")
    horizontal_status = record.get("horizontalCrsStatus", "Declared")
    vertical_status = record.get("verticalDatumStatus", "Declared")
    collar_accuracy_status = record.get("collarElevationAccuracyStatus")
    horizontal_accuracy_status = record.get("horizontalPositionAccuracyStatus")
    allowed_reference_status = {"Declared", "Verified", "AuthorityInferred", "Unverified"}
    if horizontal_status not in allowed_reference_status or vertical_status not in allowed_reference_status:
        raise ValueError("invalid coordinate-reference evidence status")
    if collar_accuracy_status is not None and collar_accuracy_status not in allowed_reference_status:
        raise ValueError("invalid collar-elevation accuracy status")
    allowed_horizontal_accuracy = {"Declared", "Verified", "DeclaredResolutionOnly", "Unverified"}
    if horizontal_accuracy_status is not None and horizontal_accuracy_status not in allowed_horizontal_accuracy:
        raise ValueError("invalid horizontal-position accuracy status")
    constraint_authorized = (horizontal_status in {"Declared", "Verified"} and
                             vertical_status in {"Declared", "Verified"} and
                             collar_accuracy_status not in {"AuthorityInferred", "Unverified"} and
                             horizontal_accuracy_status not in {"DeclaredResolutionOnly", "Unverified"})
    result = {key:record[key] for key in required if key != "intervals"} | {
        "intervals":intervals, "normalizationState":"EvidenceNormalized_NoCorrelation",
        "sourceCoordinatePreserved":[float(record["longitude"]),float(record["latitude"])],
        "horizontalCrsStatus":horizontal_status,
        "verticalDatumStatus":vertical_status,
        "elevationConstraintAuthorized":constraint_authorized}
    if collar_accuracy_status is not None:
        result["collarElevationAccuracyStatus"] = collar_accuracy_status
    if horizontal_accuracy_status is not None:
        result["horizontalPositionAccuracyStatus"] = horizontal_accuracy_status
    return result


def apply_geographic_transform_record(borehole: Mapping, transform: Mapping,
                                      *, maximum_operation_accuracy_m=2.0):
    """Apply a hash-bound, externally computed geographic CRS transformation.

    The operation record must bind the exact source coordinate and CRS.  This
    function deliberately does not calculate a datum shift or infer a CRS.
    """
    hole = normalize_borehole(borehole)
    if not isinstance(transform, Mapping) or transform.get("schemaVersion") != "GeographicEvidenceTransform-1.0":
        raise ValueError("unsupported coordinate-transform evidence")
    claimed = transform.get("recordSha256")
    unsigned = {k:v for k,v in transform.items() if k != "recordSha256"}
    actual = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()
    if not isinstance(claimed, str) or claimed != actual:
        raise ValueError("coordinate-transform evidence hash mismatch")
    if transform.get("sourceId") != hole["sourceId"]:
        raise ValueError("coordinate-transform source binding mismatch")
    if transform.get("sourceCrs") != hole["horizontalCrs"]:
        raise ValueError("coordinate-transform source CRS mismatch")
    if transform.get("targetCrs") not in {"EPSG:6668", "JGD2011"}:
        raise ValueError("coordinate-transform target must be JGD2011")
    source_xy, target_xy = transform.get("sourceLonLat"), transform.get("targetLonLat")
    residual = transform.get("roundTripResidualDegrees")
    if any(not isinstance(v, list) or len(v) != 2 for v in (source_xy,target_xy,residual)):
        raise ValueError("coordinate-transform coordinate arrays are invalid")
    flat = list(source_xy)+list(target_xy)+list(residual)
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in flat):
        raise ValueError("coordinate-transform values must be finite numbers")
    if any(abs(float(source_xy[i])-hole["sourceCoordinatePreserved"][i]) > 1e-12 for i in range(2)):
        raise ValueError("coordinate-transform source coordinate mismatch")
    if max(abs(float(v)) for v in residual) > 1e-10:
        raise ValueError("coordinate-transform round-trip residual is excessive")
    accuracy = transform.get("operationAccuracyM")
    if (isinstance(accuracy,bool) or not isinstance(accuracy,(int,float)) or
            not math.isfinite(accuracy) or accuracy < 0 or
            accuracy > maximum_operation_accuracy_m):
        raise ValueError("coordinate-transform operation accuracy is unacceptable")
    transformed = normalize_borehole({
        **{k:hole[k] for k in ("boreholeId","collarElevationM","totalDepthM",
            "verticalDatum","sourceId","sourceUrl","exchangeFormatVersion")},
        "longitude":float(target_xy[0]), "latitude":float(target_xy[1]),
        "horizontalCrs":"EPSG:6668", "intervals":hole["intervals"],
        "horizontalCrsStatus":"Verified",
        "verticalDatumStatus":hole["verticalDatumStatus"],
        **({"collarElevationAccuracyStatus":hole["collarElevationAccuracyStatus"]}
           if "collarElevationAccuracyStatus" in hole else {}),
        **({"horizontalPositionAccuracyStatus":hole["horizontalPositionAccuracyStatus"]}
           if "horizontalPositionAccuracyStatus" in hole else {}),
    })
    transformed.update({
        "sourceCoordinatePreserved":list(map(float,source_xy)),
        "transformedCoordinatePreserved":list(map(float,target_xy)),
        "coordinateTransformEvidence":dict(transform),
        "coordinateTransformState":"EvidenceBoundTransformation_NoVerticalDatumChange",
    })
    return transformed


def apply_vertical_datum_interpretation(borehole: Mapping, interpretation: Mapping,
                                        source_artifact_sha256: str):
    """Bind a national height definition while preserving unknown accuracy."""
    hole=normalize_borehole(borehole)
    if (not isinstance(interpretation,Mapping) or
            interpretation.get("schemaVersion")!="VerticalDatumInterpretation-1.0"):
        raise ValueError("unsupported vertical datum interpretation")
    claimed=interpretation.get("recordSha256")
    unsigned={k:v for k,v in interpretation.items() if k!="recordSha256"}
    actual=hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()
    if claimed!=actual:raise ValueError("vertical datum interpretation hash mismatch")
    if interpretation.get("boreholeSourceId")!=hole["sourceId"]:
        raise ValueError("vertical datum interpretation source mismatch")
    if (not isinstance(source_artifact_sha256,str) or len(source_artifact_sha256)!=64 or
            any(c not in "0123456789abcdef" for c in source_artifact_sha256) or
            interpretation.get("sourceArtifactSha256")!=source_artifact_sha256):
        raise ValueError("vertical datum source artifact mismatch")
    if interpretation.get("sourceHeightTerm")!="標高":
        raise ValueError("source height term is not the Japanese legal altitude term")
    if interpretation.get("applicability")!="JapanMainIslands_NonExceptionalHeightDatum":
        raise ValueError("national height definition applicability is not established")
    if interpretation.get("resolvedVerticalDatum")!="TokyoBayMeanSeaLevel_JapanHeightDatum":
        raise ValueError("resolved vertical datum is unsupported")
    updated={**borehole,
      "verticalDatum":interpretation["resolvedVerticalDatum"],
      "verticalDatumStatus":"Verified",
      "verticalDatumInterpretationEvidence":dict(interpretation),
      "collarElevationAccuracyStatus":interpretation.get("collarElevationAccuracyStatus","Unverified")}
    result=normalize_borehole(updated)
    result["verticalDatumInterpretationEvidence"]=dict(interpretation)
    result["collarElevationAccuracyStatus"]=updated["collarElevationAccuracyStatus"]
    result["elevationConstraintAuthorized"]=(result["elevationConstraintAuthorized"] and
        result["collarElevationAccuracyStatus"] in {"Declared","Verified"})
    return result


def project_boreholes_to_geographic_route(boreholes: Sequence[Mapping], route,
                                           maximum_offset_m):
    """Project normalized holes to a route using a local tangent-plane metric."""
    if isinstance(maximum_offset_m, bool) or not isinstance(maximum_offset_m,(int,float)) or maximum_offset_m < 0:
        raise ValueError("maximum_offset_m must be non-negative")
    # Use route latitude as a local metric transform for kilometre-scale screening.
    vertices = route
    if not isinstance(vertices, Sequence) or len(vertices) < 2:
        raise ValueError("route must contain at least two longitude/latitude vertices")
    lat0 = sum(float(p[1]) for p in vertices)/len(vertices)
    scale_x = 6378137.0*math.cos(math.radians(lat0))*math.pi/180
    scale_y = 6378137.0*math.pi/180
    from .map_template import MeasuredRoute2D
    projected_route = MeasuredRoute2D([[float(p[0])*scale_x,float(p[1])*scale_y]
                                       for p in vertices])
    output=[]
    for source in boreholes:
        hole=normalize_borehole(source)
        if hole["horizontalCrs"] not in {"JGD2011", "EPSG:6668"}:
            raise ValueError("geographic route projection requires JGD2011 / EPSG:6668 boreholes")
        result=projected_route.project([[hole["longitude"]*scale_x,hole["latitude"]*scale_y]])
        offset=float(result["projectionDistance"][0])
        reference_reasons=[]
        if hole["horizontalCrsStatus"] not in {"Declared","Verified"}:
            reference_reasons.append("HorizontalReferenceNotVerified")
        if hole["verticalDatumStatus"] not in {"Declared","Verified"}:
            reference_reasons.append("VerticalDatumNotVerified")
        if hole.get("collarElevationAccuracyStatus") in {"AuthorityInferred","Unverified"}:
            reference_reasons.append("CollarElevationAccuracyNotVerified")
        if hole.get("horizontalPositionAccuracyStatus") in {"DeclaredResolutionOnly","Unverified"}:
            reference_reasons.append("HorizontalPositionAccuracyNotVerified")
        output.append({"boreholeId":hole["boreholeId"], "sourceId":hole["sourceId"],
            "sourceLonLat":hole["sourceCoordinatePreserved"],
            "stationM":float(result["station"][0]), "projectionDistanceM":offset,
            "projectionState":"Projected" if offset <= maximum_offset_m and hole["elevationConstraintAuthorized"] else "Rejected",
            "projectionRejectionReasons":(["RouteOffsetExceeded"] if offset > maximum_offset_m else []) +
                reference_reasons,
            "collarElevationM":float(hole["collarElevationM"]),
            "verticalDatum":hole["verticalDatum"],
            "horizontalCrsStatus":hole["horizontalCrsStatus"],
            "verticalDatumStatus":hole["verticalDatumStatus"],
            **({"collarElevationAccuracyStatus":hole["collarElevationAccuracyStatus"]}
               if "collarElevationAccuracyStatus" in hole else {}),
            **({"horizontalPositionAccuracyStatus":hole["horizontalPositionAccuracyStatus"]}
               if "horizontalPositionAccuracyStatus" in hole else {}),
            "elevationConstraintAuthorized":hole["elevationConstraintAuthorized"],
            "intervals":hole["intervals"]})
    return output


def screen_boreholes_to_geographic_route(boreholes: Sequence[Mapping], route,
                                          *, coordinate_assumption: str):
    """Measure candidate proximity without authorizing unverified coordinates.

    Discovery catalogues sometimes provide longitude and latitude while omitting
    their geodetic datum. Such coordinates can prioritize follow-up research, but
    cannot constrain a section. This operation therefore always remains screen-only.
    """
    if not isinstance(coordinate_assumption, str) or not coordinate_assumption.strip():
        raise ValueError("a non-empty coordinate screening assumption is required")
    if not isinstance(route, Sequence) or len(route) < 2:
        raise ValueError("route must contain at least two longitude/latitude vertices")
    vertices = []
    for point in route:
        if not isinstance(point, Sequence) or len(point) != 2:
            raise ValueError("route coordinates must be longitude/latitude pairs")
        pair = [float(point[0]), float(point[1])]
        if not all(math.isfinite(v) for v in pair):
            raise ValueError("route coordinates must be finite")
        vertices.append(pair)
    lat0 = sum(p[1] for p in vertices) / len(vertices)
    scale_x = 6378137.0 * math.cos(math.radians(lat0)) * math.pi / 180
    scale_y = 6378137.0 * math.pi / 180
    from .map_template import MeasuredRoute2D
    projected_route = MeasuredRoute2D([[p[0] * scale_x, p[1] * scale_y]
                                       for p in vertices])
    output = []
    for source in boreholes:
        hole = normalize_borehole(source)
        result = projected_route.project([[
            hole["longitude"] * scale_x, hole["latitude"] * scale_y]])
        output.append({
            "boreholeId": hole["boreholeId"],
            "sourceId": hole["sourceId"],
            "sourceLonLat": hole["sourceCoordinatePreserved"],
            "stationM": float(result["station"][0]),
            "projectionDistanceM": float(result["projectionDistance"][0]),
            "routeSegmentIndex": int(result["routeSegmentIndex"][0]),
            "screeningState": "ApproximateDiscoveryScreenOnly",
            "coordinateAssumption": coordinate_assumption.strip(),
            "sectionConstraintAuthorized": False,
            "authorizationBlockers": [
                "ScreeningOperationIsNotCoordinateTransformationEvidence",
                "VerifiedProjectionAndVerticalReferenceStillRequired",
            ],
        })
    return output
