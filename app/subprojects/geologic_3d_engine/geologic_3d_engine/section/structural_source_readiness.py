"""Audit whether captured map layers contain direct structural observations.

The audit separates measured or source-map orientations from orientations
derived by fitting mapped contacts to a DEM.  Derived orientations may diagnose
geometry, but never satisfy the direct-observation gate.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


DIRECT_BASES = {"DirectFieldMeasurement", "DigitizedSourceMapOrientationSymbol"}
DERIVED_BASES = {"MappedContactDemPlaneFit", "SyntheticAssumption"}


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def audit_structural_source_readiness(records: Sequence[Mapping]):
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise ValueError("structural-source records must be a sequence")
    rows = []
    direct_count = derived_count = 0
    for record in records:
        required = {"recordId", "sourceId", "sourceUrl", "basis",
                    "featureCount", "orientationCount"}
        if not isinstance(record, Mapping) or not required.issubset(record):
            raise ValueError("structural-source record is incomplete")
        if not all(_nonempty(record[key]) for key in
                   ("recordId", "sourceId", "sourceUrl", "basis")):
            raise ValueError("structural-source identity and provenance are required")
        feature_count = record["featureCount"]
        orientation_count = record["orientationCount"]
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
               for value in (feature_count, orientation_count)):
            raise ValueError("feature and orientation counts must be non-negative integers")
        if orientation_count > feature_count:
            raise ValueError("orientation count cannot exceed feature count")
        basis = record["basis"]
        if basis not in DIRECT_BASES | DERIVED_BASES | {"NoOrientationSemantics"}:
            raise ValueError("unsupported structural-source basis")
        if basis == "NoOrientationSemantics" and orientation_count:
            raise ValueError("a non-orientation layer cannot declare orientations")
        if basis in DIRECT_BASES:
            required_orientation = {"trueDipDegrees", "dipDirectionDegrees",
                                    "angularUncertaintyDegrees"}
            observations = record.get("orientations")
            if not isinstance(observations, list) or len(observations) != orientation_count:
                raise ValueError("direct orientation records must include every observation")
            for observation in observations:
                if not isinstance(observation, Mapping) or not required_orientation.issubset(observation):
                    raise ValueError("direct orientation observation is incomplete")
                dip = observation["trueDipDegrees"]
                direction = observation["dipDirectionDegrees"]
                uncertainty = observation["angularUncertaintyDegrees"]
                if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
                       not math.isfinite(value) for value in (dip, direction, uncertainty)):
                    raise ValueError("orientation values must be finite numbers")
                if not 0 <= dip < 90 or not 0 <= direction < 360 or uncertainty < 0:
                    raise ValueError("orientation values are outside their declared domains")
            direct_count += orientation_count
            role = "DirectStructuralConstraintCandidate"
        elif basis in DERIVED_BASES:
            derived_count += orientation_count
            role = "DiagnosticOnly_NotDirectObservation"
        else:
            role = "NoStructuralOrientationContent"
        rows.append({
            "recordId": record["recordId"],
            "sourceId": record["sourceId"],
            "basis": basis,
            "featureCount": feature_count,
            "orientationCount": orientation_count,
            "constraintRole": role,
            "directConstraintAuthorized": basis in DIRECT_BASES and orientation_count > 0,
        })
    return {
        "schemaVersion": "StructuralSourceReadinessAudit-1.0",
        "recordCount": len(rows),
        "directOrientationCount": direct_count,
        "derivedDiagnosticOrientationCount": derived_count,
        "directStructuralConstraintAvailable": direct_count > 0,
        "records": rows,
        "authorizationBoundary":
            "DirectObservationsOnly_DemContactFitsAndSyntheticOrientationsExcluded",
    }
