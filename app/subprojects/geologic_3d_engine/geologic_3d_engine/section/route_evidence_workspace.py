"""Assemble route-bound observations without inventing subsurface geometry."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .route_binding import build_route_binding, require_matching_route_binding


def _load(path, schema):
    source = Path(path)
    raw = source.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict) or value.get("schemaVersion") != schema:
        raise ValueError(f"{schema} is required")
    return value, hashlib.sha256(raw).hexdigest()


def assemble_route_evidence_workspace(plan_path, *, borehole_path=None,
                                      structural_path=None):
    plan, plan_hash = _load(plan_path, "PlanEvidenceBundle-1.0")
    route = plan.get("routeLonLat")
    terrain = plan.get("terrainProfile")
    if not isinstance(terrain, list) or not terrain:
        raise ValueError("plan terrain profile is required")
    terminal = terrain[-1].get("stationM") if isinstance(terrain[-1], dict) else None
    if (isinstance(terminal, bool) or not isinstance(terminal, (int, float)) or
            not math.isfinite(terminal) or terminal <= 0):
        raise ValueError("plan requires a positive terminal station")
    artifacts = {"planEvidence": plan_hash}
    boreholes = []
    if borehole_path:
        document, digest = _load(borehole_path, "BoreholeSectionIntake-1.0")
        require_matching_route_binding(route, document, "borehole intake")
        artifacts["boreholeIntake"] = digest
        boreholes = list(document.get("boreholes", []))
    observations = []
    if structural_path:
        document, digest = _load(structural_path, "StructuralObservationProjection-1.0")
        require_matching_route_binding(route, document, "structural observations")
        artifacts["structuralObservations"] = digest
        observations = list(document.get("observations", []))
    station_rows = [row for row in [*boreholes, *observations]
                    if isinstance(row, dict) and row.get("projectionState") == "Projected"]
    if any(isinstance(row.get("stationM"), bool) or
           not isinstance(row.get("stationM"), (int, float)) or
           not math.isfinite(row["stationM"]) or not 0 <= row["stationM"] <= terminal
           for row in station_rows):
        raise ValueError("projected evidence station lies outside the bound route")
    payload = {
        "schemaVersion": "RouteEvidenceWorkspace-1.0",
        "routeBinding": build_route_binding(route),
        "terrainProfile": terrain,
        "surfaceGeology": plan.get("surfaceGeology"),
        "mappedLineworkEvidence": plan.get("mappedLineworkEvidence"),
        "boreholes": boreholes,
        "structuralObservations": observations,
        "inputArtifactSha256": artifacts,
        "authorizationState": "EvidenceOverlayOnly_NoAutomaticSubsurfaceGeometry",
        "unknownPolicy": "NoEvidenceRemainsUnknown_NoInterpolationAcrossEvidenceGaps",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    payload["recordSha256"] = hashlib.sha256(canonical).hexdigest()
    return payload
