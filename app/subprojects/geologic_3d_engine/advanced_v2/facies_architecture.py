"""Plan how candidate lithologies may be portrayed without inventing geometry."""
from __future__ import annotations

POLICY_ID = "ADV2-FACIES-ARCHITECTURE-1.0"

MINIMUM_GEOMETRIC_BODIES = {
    "UnconsolidatedSedimentTerrain": 12,
    "SedimentaryRockTerrain": 13,
    "VolcanicTerrain": 15,
    "PlutonicTerrain": 7,
    "AccretionaryComplex": 5,
    "MetamorphicBelt": 4,
}

ARCHITECTURES = {
    "UnconsolidatedSedimentTerrain": {
        "mode": "SequentialStratifiedPackages",
        "geometricRoles": {"SurfaceCover", "FineSediment", "CoarseSediment", "DisplayBase"},
        "compositionRoles": set(),
    },
    "SedimentaryRockTerrain": {
        "mode": "SequentialStratifiedPackages",
        "geometricRoles": {"SurfaceCover", "FineClastic", "CoarseClastic", "AlternatingClastic",
                           "VolcaniclasticMarker", "DisplayBase"},
        "compositionRoles": set(),
    },
    "VolcanicTerrain": {
        "mode": "VolcanicPackageStack_NoLocalVentGeometry",
        "geometricRoles": {"SurfaceCover", "Tephra", "EdificeRockMass", "Pyroclastic",
                           "LavaBreccia", "Lava", "AlteredVolcanic", "DisplayBase"},
        "compositionRoles": set(),
    },
    "PlutonicTerrain": {
        "mode": "WeatheringStateProfile",
        "geometricRoles": {"SurfaceCover", "WeatheringState", "FractureState", "FreshRock", "DisplayBase"},
        "compositionRoles": set(),
    },
    "AccretionaryComplex": {
        "mode": "MatrixWithUnlocatedCompositionParts",
        "geometricRoles": {"SurfaceCover", "WeatheringState", "Matrix", "MixedComplex", "DisplayBase"},
        "compositionRoles": {"BlockOrSlice"},
    },
    "MetamorphicBelt": {
        "mode": "MetamorphicPackage_NoInventedLithologicZonation",
        "geometricRoles": {"SurfaceCover", "WeatheringState", "FoliatedMixed", "DisplayBase"},
        "compositionRoles": {"Metasedimentary"},
    },
}


def plan_facies_architecture(domain: str, rows: list[tuple]) -> dict:
    policy = ARCHITECTURES.get(domain)
    if policy is None:
        return {"policyId": POLICY_ID, "passed": False, "errors": ["UnsupportedDomain"]}
    geometric, composition, errors = [], [], []
    seen = set()
    for row in rows:
        unit_id, role = row[0], row[4]
        if unit_id in seen:
            errors.append("DuplicateUnitId:" + unit_id)
        seen.add(unit_id)
        if role in policy["geometricRoles"]:
            geometric.append(row)
        elif role in policy["compositionRoles"]:
            composition.append(row)
        else:
            errors.append("RoleNotAuthorized:" + role)
    if not geometric or geometric[-1][4] != "DisplayBase":
        errors.append("DisplayBaseMissingOrNotLast")
    minimum = MINIMUM_GEOMETRIC_BODIES[domain]
    if len(geometric) < minimum:
        errors.append(f"InsufficientGeometricLithologyDiversity:{len(geometric)}<{minimum}")
    return {
        "policyId": POLICY_ID,
        "passed": not errors,
        "errors": errors,
        "domain": domain,
        "architectureMode": policy["mode"],
        "geometricRows": geometric,
        "compositionRows": composition,
        "candidateLithologyCount": len(rows),
        "geometricBodyCount": len(geometric),
        "minimumGeometricBodyCount": minimum,
        "compositionPartCount": len(composition),
        "localizedGeometryInvented": False,
    }


def audit_facies_portrayal(model: dict) -> dict:
    """Prove that unlocated composition candidates did not become bodies."""
    architecture = model.get("faciesArchitecture", {})
    parts = architecture.get("compositionParts", [])
    body_ids = {row.get("unitId") for row in model.get(
        "syntheticEventArchitecture", {}).get("renderBodies", [])}
    unauthorized = sorted(row.get("unitId") for row in parts
                          if row.get("unitId") in body_ids)
    errors = ["UnlocatedCompositionPartRendered:" + value for value in unauthorized]
    if architecture.get("candidateLithologyCount", 0) < architecture.get("geometricBodyCount", 0):
        errors.append("CandidateCountBelowGeometricBodyCount")
    minimum = MINIMUM_GEOMETRIC_BODIES.get(architecture.get("domain"))
    if minimum is not None and architecture.get("geometricBodyCount", 0) < minimum:
        errors.append("InsufficientGeometricLithologyDiversity")
    if any(row.get("geometryAuthorized") is not False for row in parts):
        errors.append("CompositionPartAuthorizationAmbiguous")
    return {"policyId": POLICY_ID, "passed": not errors, "errors": errors,
        "renderedBodyCount": len(body_ids), "unlocatedCompositionPartCount": len(parts),
        "unauthorizedRenderedPartCount": len(unauthorized), "localizedGeometryInvented": False}
