"""Classify borehole route roles without projecting distant contacts as geometry."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .borehole_evidence import normalize_borehole
from .map_template import MeasuredRoute2D


def _project(route, longitude, latitude):
    lat0 = sum(float(p[1]) for p in route)/len(route)
    sx = 6378137.0*math.cos(math.radians(lat0))*math.pi/180
    sy = 6378137.0*math.pi/180
    measured = MeasuredRoute2D([[float(p[0])*sx, float(p[1])*sy] for p in route])
    result = measured.project([[longitude*sx, latitude*sy]])
    segment = int(result["routeSegmentIndex"][0])
    station = float(result["station"][0])
    a, b = route[segment], route[segment + 1]
    segment_start = measured.stations[segment]
    fraction = ((station-segment_start)/measured.segment_lengths[segment]
                if measured.segment_lengths[segment] else 0.0)
    projected = [float(a[0])+(float(b[0])-float(a[0]))*fraction,
                 float(a[1])+(float(b[1])-float(a[1]))*fraction]
    return station, float(result["projectionDistance"][0]), segment, projected


def classify_borehole_route_roles(boreholes: Sequence[Mapping], route_lonlat,
                                   constraint_offset_m: float,
                                   context_offset_m: float):
    thresholds = (constraint_offset_m, context_offset_m)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) or v < 0 for v in thresholds):
        raise ValueError("route-role offsets must be finite non-negative numbers")
    if context_offset_m < constraint_offset_m:
        raise ValueError("context offset must be at least the constraint offset")
    if (not isinstance(route_lonlat, Sequence) or isinstance(route_lonlat, (str, bytes))
            or len(route_lonlat) < 2):
        raise ValueError("route requires at least two vertices")
    output = []
    for source in boreholes:
        hole = normalize_borehole(source)
        if hole["horizontalCrs"] not in {"JGD2011", "EPSG:6668"}:
            raise ValueError("route-role classification requires JGD2011 coordinates")
        station, distance, segment, projected = _project(
            route_lonlat, hole["longitude"], hole["latitude"])
        quality_blockers = []
        if hole["horizontalCrsStatus"] != "Verified":
            quality_blockers.append("HorizontalCrsNotVerified")
        if hole["verticalDatumStatus"] != "Verified":
            quality_blockers.append("VerticalDatumNotVerified")
        if hole.get("collarElevationAccuracyStatus") not in {"Declared", "Verified"}:
            quality_blockers.append("CollarElevationAccuracyNotVerified")
        if hole.get("horizontalPositionAccuracyStatus") not in {"Declared", "Verified"}:
            quality_blockers.append("HorizontalPositionAccuracyNotVerified")
        if any(row.get("evidenceStatus") not in {"Observed", "Literature"}
               for row in hole["intervals"]):
            quality_blockers.append("IntervalsNotEvidenceQualified")
        if distance <= constraint_offset_m and not quality_blockers:
            role = "DirectSectionConstraintCandidate"
            geometry_authorized = bool(hole["elevationConstraintAuthorized"])
        elif distance <= context_offset_m:
            role = "RegionalContextOnly"
            geometry_authorized = False
        else:
            role = "OutsideDeclaredContextRange"
            geometry_authorized = False
        output.append({"boreholeId": hole["boreholeId"], "sourceId": hole["sourceId"],
            "stationM": station, "projectionDistanceM": distance,
            "routeSegmentIndex": segment, "role": role,
            "qualityBlockers": quality_blockers,
            "sectionGeometryAuthorized": geometry_authorized,
            "contextMayBeDisplayed": role == "RegionalContextOnly",
            "contextDisplayBoundary": "LocationAndSourceSummaryOnly_NoProjectedContacts",
            "sourceLonLat": [hole["longitude"], hole["latitude"]],
            "nearestRouteLonLat": projected})
    return {"schemaVersion": "BoreholeRouteRoleClassification-1.0",
        "constraintOffsetM": float(constraint_offset_m),
        "contextOffsetM": float(context_offset_m), "boreholes": output,
        "directConstraintCandidateCount": sum(x["role"] == "DirectSectionConstraintCandidate" for x in output),
        "regionalContextCount": sum(x["role"] == "RegionalContextOnly" for x in output),
        "outsideContextCount": sum(x["role"] == "OutsideDeclaredContextRange" for x in output),
        "authorizationBoundary": "DistanceAndEvidenceRoleClassification_NoAutomaticCorrelation"}
