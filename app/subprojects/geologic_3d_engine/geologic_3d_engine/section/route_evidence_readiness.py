"""Fail-closed evidence readiness for an arbitrary geological section route."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence


def _finite_number(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float)) and
            math.isfinite(value))


def audit_constraint_station_distribution(route_length_m, constraints):
    """Describe along-route evidence spacing without inventing support radii."""
    if not _finite_number(route_length_m) or route_length_m <= 0:
        raise ValueError("route_length_m must be positive")
    rows = list(constraints)
    if any(not isinstance(row, Mapping) or not _finite_number(row.get("stationM"))
           for row in rows):
        raise ValueError("every constraint requires a finite stationM")
    stations = sorted(float(row["stationM"]) for row in rows)
    if any(station < 0 or station > route_length_m for station in stations):
        raise ValueError("constraint station lies outside the route")
    gaps = ([float(route_length_m)] if not stations else
            [stations[0], *(b-a for a, b in zip(stations, stations[1:])),
             float(route_length_m)-stations[-1]])
    return {
        "routeLengthM": float(route_length_m),
        "constraintStationCount": len(stations),
        "constraintStationsM": stations,
        "startEndpointGapM": gaps[0],
        "endEndpointGapM": gaps[-1],
        "maximumUnbracketedGapM": max(gaps),
        "bracketedIntervalCount": max(0, len(stations)-1),
        "coverageInterpretation": ("NoDirectConstraintStations" if not stations else
            "SpacingDiagnosticOnly_NoInterpolationRadiusAuthorized"),
    }


def assess_route_evidence_readiness(plan_bundle: Mapping, *, mapped_crossings=None,
                                    boreholes=(), structural_observations=(),
                                    contact_plane_diagnostics=None,
                                    reviewed_geometry=(), input_artifact_sha256=None):
    """Classify what may be generated without promoting context to constraints.

    A mapped contact or a DEM-following local plane is surface evidence only.
    Subsurface geometry is authorized only by an explicit accepted geometry
    binding supplied by a separate review stage.
    """
    if not isinstance(plan_bundle, Mapping) or plan_bundle.get("schemaVersion") != "PlanEvidenceBundle-1.0":
        raise ValueError("a PlanEvidenceBundle-1.0 is required")
    route = plan_bundle.get("routeLonLat")
    profile = plan_bundle.get("terrainProfile")
    if (not isinstance(route, Sequence) or len(route) < 2 or
            not isinstance(profile, Sequence) or not profile):
        raise ValueError("route and terrain profile are required")
    terrain_valid = sum(1 for row in profile if isinstance(row, Mapping) and
                        _finite_number(row.get("elevationM")))
    terrain_complete = terrain_valid == len(profile)

    transitions = []
    if mapped_crossings is not None:
        if (not isinstance(mapped_crossings, Mapping) or
                mapped_crossings.get("schemaVersion") != "GsjRouteCrossingSideClassification-1.0"):
            raise ValueError("mapped crossing evidence has an unsupported schema")
        transitions = [row for row in mapped_crossings.get("crossings", [])
                       if row.get("sideClassificationStatus") == "MappedUnitTransition"]
    elif isinstance(plan_bundle.get("surfaceGeology"), Mapping):
        # Point-sampled transitions remain interval-censored surface evidence.
        transitions = list(plan_bundle["surfaceGeology"].get("transitions", []))

    borehole_rows = list(boreholes)
    direct_boreholes = [row for row in borehole_rows
                        if row.get("projectionState") == "Projected" and
                        row.get("elevationConstraintAuthorized") is True]
    rejected_boreholes = [row for row in borehole_rows
                          if row.get("projectionState") == "Rejected"]
    orientation_rows = list(structural_observations)
    direct_orientations = [row for row in orientation_rows
                           if row.get("projectionState") == "Projected" and
                           isinstance(row.get("sourceId"), str) and row.get("sourceId")]

    diagnostic_rows = []
    if contact_plane_diagnostics is not None:
        if (not isinstance(contact_plane_diagnostics, Mapping) or
                contact_plane_diagnostics.get("schemaVersion") != "MappedContactDemPlaneDiagnostics-1.0"):
            raise ValueError("contact-plane diagnostics have an unsupported schema")
        diagnostic_rows = list(contact_plane_diagnostics.get("diagnostics", []))
    authorized_planes = [row for row in diagnostic_rows
                         if row.get("subsurfaceContinuationAuthorized") is True]

    bindings = list(reviewed_geometry)
    if any(not isinstance(row, Mapping) for row in bindings):
        raise ValueError("reviewed geometry records must be objects")
    accepted_bindings = [row for row in bindings
                         if row.get("reviewStatus") == "Accepted" and
                         row.get("artifactBound") is True]
    constraint_rows = [*direct_boreholes, *direct_orientations, *authorized_planes]
    route_length = profile[-1].get("stationM") if isinstance(profile[-1], Mapping) else None
    if not _finite_number(route_length) or route_length <= 0:
        # Older minimal bundles may omit stationM; preserve their readiness
        # result while making the unavailable spatial diagnosis explicit.
        station_distribution = {"coverageInterpretation":
                                "Unavailable_ProfileHasNoPositiveTerminalStation"}
    else:
        station_distribution = audit_constraint_station_distribution(route_length,
            [row for row in constraint_rows if _finite_number(row.get("stationM"))])
    artifact_hashes = dict(input_artifact_sha256 or {})
    if any(not isinstance(key, str) or not key or not isinstance(value, str) or
           len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
           for key, value in artifact_hashes.items()):
        raise ValueError("input artifact hashes must be named lowercase SHA-256 values")

    candidate_count = len(direct_boreholes) + len(direct_orientations) + len(authorized_planes)
    section_authorized = (terrain_complete and bool(transitions) and
                          candidate_count > 0 and bool(accepted_bindings))
    reasons = []
    if not terrain_complete:
        reasons.append("TerrainProfileIncomplete")
    if not transitions:
        reasons.append("NoMappedGeologicTransitions")
    if candidate_count == 0:
        reasons.append("NoDirectSubsurfaceConstraintCandidates")
    if not accepted_bindings:
        reasons.append("NoArtifactBoundReviewedGeometry")
    state = ("ReviewedEvidenceConstrainedSectionAuthorized" if section_authorized else
             "EvidenceContextAvailable_SectionGeometryNotAuthorized" if terrain_complete and transitions else
             "TerrainOnlyOrIncomplete")
    payload = {
        "schemaVersion": "RouteEvidenceReadiness-1.0",
        "routeVertexCount": len(route),
        "terrainSampleCount": len(profile),
        "validTerrainSampleCount": terrain_valid,
        "terrainComplete": terrain_complete,
        "mappedTransitionCount": len(transitions),
        "mappedTransitionBasis": ("ExactVectorCrossingSideClassification"
                                  if mapped_crossings is not None else
                                  "PointSampledIntervalCensoredSurfaceTransition"
                                  if transitions else "None"),
        "boreholeCount": len(borehole_rows),
        "directBoreholeConstraintCount": len(direct_boreholes),
        "rejectedBoreholeCount": len(rejected_boreholes),
        "structuralObservationCount": len(orientation_rows),
        "directOrientationConstraintCount": len(direct_orientations),
        "contactPlaneDiagnosticCount": len(diagnostic_rows),
        "authorizedContactPlaneCount": len(authorized_planes),
        "acceptedReviewedGeometryCount": len(accepted_bindings),
        "constraintStationDistribution": station_distribution,
        "inputArtifactSha256": artifact_hashes,
        "authorizationState": state,
        "sectionGeometryAuthorized": section_authorized,
        "generationModesAuthorized": (["TerrainProfile", "MappedSurfaceIntervals"]
                                      if terrain_complete and transitions else
                                      ["TerrainProfile"] if terrain_complete else []),
        "blockingReasons": reasons,
        "boundary": "ReadinessClassification_NotAutomaticGeologicalInterpretation",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    payload["recordSha256"] = hashlib.sha256(canonical).hexdigest()
    return payload
