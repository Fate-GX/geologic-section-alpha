"""Audit the boundary between a supported compaction equation and unsupported fixture values."""

from __future__ import annotations


EXPECTED_IDS = {
    "S6-COMP-FILL-SOURCE",
    "S6-COMP-FILL-TARGET",
    "S6-COMP-UPPER-SOURCE",
    "S6-COMP-UPPER-TARGET",
    "S6-COMP-LOWER-SOURCE",
    "S6-COMP-LOWER-TARGET",
}


def audit_compaction_parameter_readiness(inventory: dict, readiness: dict) -> dict:
    errors = []
    requirements = {
        item.get("parameterId"): item
        for item in inventory.get("requirements", [])
        if str(item.get("parameterId", "")).startswith("S6-COMP-")
    }
    assessments = readiness.get("parameterAssessments", [])
    by_id = {}
    for item in assessments:
        by_id.setdefault(item.get("parameterId"), []).append(item)

    if set(requirements) != EXPECTED_IDS:
        errors.append({"code": "CompactionInventoryMismatch", "actualIds": sorted(requirements)})
    for parameter_id in sorted(EXPECTED_IDS):
        found = by_id.get(parameter_id, [])
        if len(found) != 1:
            errors.append({"code": "ReadinessCoverageMismatch", "parameterId": parameter_id, "count": len(found)})
            continue
        requirement, assessment = requirements.get(parameter_id, {}), found[0]
        if requirement.get("unit") != "1" or requirement.get("dimension") != "1":
            errors.append({"code": "PorosityMustBeDimensionless", "parameterId": parameter_id})
        if requirement.get("valueKind") != "Scalar" or not (0 <= requirement.get("value", -1) < 1):
            errors.append({"code": "InvalidPorosityFixtureValue", "parameterId": parameter_id})
        if assessment.get("currentBasisType") != "SyntheticAssumption":
            errors.append({"code": "PrematureEvidencePromotion", "parameterId": parameter_id})
        if assessment.get("readiness") != "NeedsObservedOrCompatibleLiteratureValue":
            errors.append({"code": "InvalidReadinessState", "parameterId": parameter_id})

    equation = readiness.get("equationContract", {})
    if equation.get("expression") != "phi(z)=phi0*exp(-c*z)":
        errors.append({"code": "EquationContractMismatch"})
    if equation.get("sourceStatus") != "FunctionalFormPartiallySupported_PrecisePassagePending":
        errors.append({"code": "EquationEvidenceOverclaim"})
    if len(readiness.get("requiredEvidencePerParameter", [])) < 7:
        errors.append({"code": "IncompleteEvidenceRequirements"})
    if readiness.get("status") != "EvidenceGapRecord_NotRealRegionAuthorization":
        errors.append({"code": "RealRegionAuthorizationOverclaim"})

    return {
        "passed": not errors,
        "gate": "CompactionParameterEvidenceReadiness",
        "errors": errors,
        "parameterCount": len(EXPECTED_IDS),
        "syntheticAssumptionCount": sum(
            len(by_id.get(parameter_id, [])) == 1
            and by_id[parameter_id][0].get("currentBasisType") == "SyntheticAssumption"
            for parameter_id in EXPECTED_IDS
        ),
        "realEvidenceBindingCount": 0,
        "realRegionAuthorized": False,
    }
