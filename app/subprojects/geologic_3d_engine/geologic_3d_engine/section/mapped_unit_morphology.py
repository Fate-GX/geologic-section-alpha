"""Apply source-linked morphology classes without inventing subsurface shape."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


FINITE_MORPHOLOGIES = {
    "ScoriaConeAndLavaFlowApron",
    "VentProximalLavaEdifice",
    "PumiceCone",
}
ALLOWED_MORPHOLOGIES = FINITE_MORPHOLOGIES | {"SurficialFallDepositDrape"}


def apply_mapped_unit_morphology(unit_catalog: Mapping, profile: Mapping):
    units = unit_catalog.get("units") if isinstance(unit_catalog, Mapping) else None
    records = profile.get("records") if isinstance(profile, Mapping) else None
    if not isinstance(units, list) or not isinstance(records, list):
        raise ValueError("unit catalog and morphology profile are required")
    by_symbol = {}
    for record in records:
        required = {"sourceSymbol", "morphologyClass", "sourceId", "locator",
                    "evidenceStatus", "numericSubsurfaceGeometryAuthorized"}
        if not isinstance(record, Mapping) or not required.issubset(record):
            raise ValueError("morphology record is incomplete")
        if record["sourceSymbol"] in by_symbol:
            raise ValueError("morphology source symbols must be unique")
        if record["morphologyClass"] not in ALLOWED_MORPHOLOGIES:
            raise ValueError("unsupported mapped-unit morphology")
        if record["numericSubsurfaceGeometryAuthorized"] is not False:
            raise ValueError("morphology evidence cannot authorize numeric subsurface geometry")
        if not all(isinstance(record[key], str) and record[key].strip()
                   for key in ("sourceSymbol", "sourceId", "locator", "evidenceStatus")):
            raise ValueError("morphology provenance must be non-empty")
        directions = record.get("qualitativeFlowDirections", [])
        if not isinstance(directions, list) or any(direction not in
                {"North", "Northeast", "East", "Southeast", "South",
                 "Southwest", "West", "Northwest"} for direction in directions):
            raise ValueError("qualitative flow directions are invalid")
        if record.get("numericFlowAzimuthAuthorized", False) is not False:
            raise ValueError("qualitative source wording cannot authorize numeric flow azimuth")
        by_symbol[record["sourceSymbol"]] = dict(record)
    output = []
    for unit in units:
        symbol = unit.get("symbol")
        record = by_symbol.get(symbol)
        if record is None:
            output.append({**unit, "morphologyStatus": "NeedsSourceLinkedClassification",
                           "numericSubsurfaceGeometryAuthorized": False})
            continue
        finite = record["morphologyClass"] in FINITE_MORPHOLOGIES
        output.append({
            **unit,
            "morphologyStatus": "SourceLinkedQualitativeMorphology",
            "morphologyClass": record["morphologyClass"],
            "finiteBodyRequired": finite,
            "surfacePolygonBoundsPlanExtent": True,
            "blanketLayerAuthorized": not finite,
            "qualitativeFlowDirections": list(record.get("qualitativeFlowDirections", [])),
            "numericFlowAzimuthAuthorized": False,
            "numericSubsurfaceGeometryAuthorized": False,
            "morphologySourceId": record["sourceId"],
            "morphologyLocator": record["locator"],
            "morphologyEvidenceStatus": record["evidenceStatus"],
        })
    return {
        "schemaVersion": "MappedUnitMorphologyAssignment-1.0",
        "unitCount": len(output),
        "classifiedCount": sum(row["morphologyStatus"] ==
                               "SourceLinkedQualitativeMorphology" for row in output),
        "units": output,
        "realRegionSubsurfaceGeometryAuthorized": False,
        "authorizationBoundary": "QualitativeBodyClassOnly_NoThicknessDipOrBottomSurface",
    }


def audit_declared_geometry_roles(declarations: Sequence[Mapping], assigned_units: Mapping):
    if not isinstance(declarations, Sequence) or isinstance(declarations, (str, bytes)):
        raise ValueError("geometry declarations must be a sequence")
    units = assigned_units.get("units") if isinstance(assigned_units, Mapping) else None
    if not isinstance(units, list):
        raise ValueError("morphology assignments are required")
    by_id = {row.get("unitId"): row for row in units}
    results = []
    for declaration in declarations:
        if not isinstance(declaration, Mapping) or not {
                "unitId", "geometryRole"}.issubset(declaration):
            raise ValueError("geometry-role declaration is incomplete")
        unit = by_id.get(declaration["unitId"])
        if unit is None:
            raise ValueError("geometry declaration references an unknown unit")
        role = declaration["geometryRole"]
        if role not in {"FiniteBody", "SurfaceDrape", "BlanketLayer"}:
            raise ValueError("unsupported geometry role")
        passed = not (unit.get("finiteBodyRequired") and role != "FiniteBody")
        results.append({
            "unitId": declaration["unitId"], "declaredGeometryRole": role,
            "requiredMorphologyClass": unit.get("morphologyClass"),
            "passed": passed,
            "reason": "CompatibleWithQualitativeMorphology" if passed else
                      "FiniteVolcanicBodyCannotBeDeclaredAsBlanketOrDrape",
        })
    return {"passed": all(row["passed"] for row in results), "results": results,
            "validationBoundary": "MorphologyCompatibilityOnly_NotGeometryValidation"}
