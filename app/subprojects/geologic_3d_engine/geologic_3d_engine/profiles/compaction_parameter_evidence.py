"""Strict intake validation for unit-specific compaction-porosity evidence."""

from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path

ALLOWED_BASIS = {"Observed", "Literature"}
ALLOWED_STATES = {"sourcePorosity", "targetPorosity"}
ALLOWED_LOCATORS = {"ExactPassage", "ExactTableCell", "ExactDatasetRecord"}
ALLOWED_REVIEW = {"PendingIndependentReview", "IndependentlyVerified"}


def validate_compaction_evidence_candidates(requirements, candidates, declared_source_ids, profile_id,
                                           *, artifact_root=None, trusted_review_hashes=None):
    errors = []
    required = {
        item["parameterId"]: item
        for item in requirements
        if str(item.get("parameterId", "")).startswith("S6-COMP-")
    }
    by_id = {}
    for item in candidates:
        by_id.setdefault(item.get("parameterId"), []).append(item)

    for parameter_id, requirement in required.items():
        found = by_id.get(parameter_id, [])
        if len(found) != 1:
            errors.append({"code": "CandidateCoverageMismatch", "parameterId": parameter_id, "count": len(found)})
            continue
        item = found[0]
        if item.get("profileId") != profile_id:
            errors.append({"code": "CandidateProfileMismatch", "parameterId": parameter_id})
        if item.get("implementationPath") != requirement.get("implementationPath"):
            errors.append({"code": "CandidateImplementationPathMismatch", "parameterId": parameter_id})
        if item.get("unit") != "1" or item.get("dimension") != "1":
            errors.append({"code": "CandidatePorosityUnitMismatch", "parameterId": parameter_id})
        value = item.get("value")
        if not _finite(value) or not 0 <= value < 1:
            errors.append({"code": "CandidatePorosityValueInvalid", "parameterId": parameter_id})
        if item.get("basisType") not in ALLOWED_BASIS:
            errors.append({"code": "CandidateBasisNotRealEvidence", "parameterId": parameter_id})
        if item.get("state") not in ALLOWED_STATES:
            errors.append({"code": "CandidateStateInvalid", "parameterId": parameter_id})
        if not _text(item, "unitIdentity") or not _text(item, "normalizedTerminology"):
            errors.append({"code": "CandidateUnitIdentityMissing", "parameterId": parameter_id})
        measurement = item.get("measurement", {})
        if not all(_text(measurement, key) for key in ("porosityDefinition", "method", "sampleSupport")):
            errors.append({"code": "CandidateMeasurementDefinitionMissing", "parameterId": parameter_id})
        burial = item.get("burialContext", {})
        if not all(_text(burial, key) for key in ("state", "depthDatum", "comparabilityStatement")):
            errors.append({"code": "CandidateBurialContextMissing", "parameterId": parameter_id})
        applicability = item.get("applicability", {})
        if not all(_text(applicability, key) for key in ("scope", "geographicExtent", "stratigraphicExtent")):
            errors.append({"code": "CandidateApplicabilityMissing", "parameterId": parameter_id})
        uncertainty = item.get("uncertainty", {})
        if not _finite(uncertainty.get("standardUncertainty")) or uncertainty.get("standardUncertainty", -1) < 0:
            errors.append({"code": "CandidateUncertaintyInvalid", "parameterId": parameter_id})
        locator = item.get("sourceLocator", {})
        source_id = locator.get("sourceId")
        if source_id not in set(declared_source_ids) or locator.get("locatorStatus") not in ALLOWED_LOCATORS or not _text(locator, "locator"):
            errors.append({"code": "CandidateSourceLocatorInvalid", "parameterId": parameter_id})
        if not isinstance(item.get("exclusions"), list) or not item["exclusions"]:
            errors.append({"code": "CandidateExclusionsMissing", "parameterId": parameter_id})
        if item.get("semanticReviewStatus") not in ALLOWED_REVIEW:
            errors.append({"code": "CandidateSemanticReviewStatusInvalid", "parameterId": parameter_id})
        if item.get("semanticReviewStatus") == "IndependentlyVerified" and not _sha256(item.get("artifactSha256")):
            errors.append({"code": "VerifiedCandidateArtifactHashMissing", "parameterId": parameter_id})

    for parameter_id, found in by_id.items():
        if parameter_id not in required:
            errors.append({"code": "UnexpectedCompactionCandidate", "parameterId": parameter_id, "recordCount": len(found)})

    structurally_valid_ids = set(required) - {error.get("parameterId") for error in errors if error.get("parameterId") in required}
    claimed_verified_ids = {
        parameter_id for parameter_id in structurally_valid_ids
        if by_id[parameter_id][0].get("semanticReviewStatus") == "IndependentlyVerified"
    }
    integrity_bound_ids = set()
    for parameter_id in claimed_verified_ids:
        item = by_id[parameter_id][0]
        try:
            _verify_artifacts(item, artifact_root, trusted_review_hashes or {})
            integrity_bound_ids.add(parameter_id)
        except (ValueError, OSError, TypeError, KeyError) as exc:
            errors.append({"code": "CandidateEvidenceBindingRejected", "parameterId": parameter_id,
                           "reason": str(exc)})
    return {
        "passed": not errors,
        "gate": "CompactionParameterEvidenceCandidateIntake",
        "errors": errors,
        "requiredParameterCount": len(required),
        "structurallyValidCount": len(structurally_valid_ids),
        "claimedVerifiedCount": len(claimed_verified_ids),
        "integrityBoundCount": len(integrity_bound_ids),
        "independentlyVerifiedCount": 0,
        "realRegionAuthorized": False,
        "authorizationStatus": "NotEvaluated_SeparateRegionalAndSemanticGatesRequired",
        "validationLayer": "CandidateStructureAndPinnedArtifactIntegrity_NotSemanticAuthority",
    }


def candidate_binding_sha256(item):
    """Internal v1 binding format, not the cross-language GEO3D contract.

    Bind every candidate field except review location to avoid a circular digest.
    This digest is integrity, not reviewer authentication or geological truth.
    """
    payload = {key: value for key, value in item.items() if key != "reviewPath"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _read_confined(root, relative):
    if root is None or not isinstance(relative, str) or not relative:
        raise ValueError("Missing artifact root/path")
    root = Path(root).resolve(strict=True)
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or ":" in relative:
        raise ValueError("Unsafe artifact path")
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("Linked artifact path")
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("Artifact outside root or not a file")
    return resolved.read_bytes()


def _verify_artifacts(item, root, trusted_reviews):
    evidence = _read_confined(root, item.get("artifactPath"))
    if hashlib.sha256(evidence).hexdigest() != item["artifactSha256"]:
        raise ValueError("Evidence bytes digest mismatch")
    review_bytes = _read_confined(root, item.get("reviewPath"))
    review_hash = hashlib.sha256(review_bytes).hexdigest()
    # Trust pins come from the calling application, never from the candidate JSON.
    if trusted_reviews.get(item["parameterId"]) != review_hash:
        raise ValueError("Review is not pinned by trusted caller")
    review = json.loads(review_bytes)
    if not isinstance(review, dict):
        raise ValueError("Review must be an object")
    if review.get("recordKind") != "RealEvidenceReview" or review.get("decision") != "SupportsCandidate":
        raise ValueError("Synthetic or non-supporting review")
    if review.get("bindingVersion") != "CandidateEvidenceBinding-1":
        raise ValueError("Unsupported review binding version")
    if review.get("candidateSha256") != candidate_binding_sha256(item):
        raise ValueError("Review candidate binding mismatch")
    if not _text(review, "reviewerId"):
        raise ValueError("Missing reviewer identity")


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _text(obj, key):
    return isinstance(obj, dict) and isinstance(obj.get(key), str) and bool(obj[key].strip())


def _sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
