"""Build a surface-control group only from an artifact-bound expert review."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from .evidence_bounded_surface import audit_surface_controls
from .evidence_bounded_surface import EvidenceBoundedRbfSurface
from .route_surface_projection import project_surface_to_route_samples
from .exact_route_hull_intersection import intersect_route_with_evidence_hull


def canonical_sha256(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_reviewed_surface_control_group(candidate_registry: Mapping,
                                         review: Mapping) -> dict:
    """Select controls explicitly; never correlate by label, depth, or proximity."""
    if candidate_registry.get("schemaVersion") != "SurfaceControlCandidateRegistry-1.0":
        raise ValueError("a SurfaceControlCandidateRegistry-1.0 is required")
    candidates = candidate_registry.get("candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise ValueError("candidate registry must contain candidates")
    required_review = {"schemaVersion", "reviewId", "reviewerId", "reviewedAt",
                       "reviewStatus", "candidateRegistrySha256", "contactId",
                       "selectedControlIds"}
    if not isinstance(review, Mapping) or not required_review.issubset(review):
        raise ValueError("surface-control review is incomplete")
    if review["schemaVersion"] != "SurfaceControlCorrelationReview-1.0":
        raise ValueError("unsupported surface-control review schema")
    if review["reviewStatus"] != "IndependentlyReviewed":
        raise ValueError("an IndependentlyReviewed correlation is required")
    if review["candidateRegistrySha256"] != canonical_sha256(candidate_registry):
        raise ValueError("review is not bound to this candidate registry")
    for key in ("reviewId", "reviewerId", "reviewedAt", "contactId"):
        if not isinstance(review[key], str) or not review[key].strip():
            raise ValueError(f"{key} is required")
    selected = review["selectedControlIds"]
    if (not isinstance(selected, Sequence) or isinstance(selected, (str, bytes))
            or len(selected) < 3 or len(set(selected)) != len(selected)):
        raise ValueError("at least three unique selected control IDs are required")
    by_id = {}
    for item in candidates:
        if not isinstance(item, Mapping) or not isinstance(item.get("controlId"), str):
            raise ValueError("every candidate requires a controlId")
        if item["controlId"] in by_id:
            raise ValueError("candidate control IDs must be unique")
        by_id[item["controlId"]] = item
    if any(control_id not in by_id for control_id in selected):
        raise ValueError("review selects an unknown control")
    controls = []
    for control_id in selected:
        candidate = by_id[control_id]
        digest = candidate.get("sourceArtifactSha256")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)):
            raise ValueError("selected control lacks a valid source artifact hash")
        controls.append({
            "xM": candidate.get("xM"), "yM": candidate.get("yM"),
            "zM": candidate.get("zM"), "contactId": review["contactId"],
            "evidenceStatus": candidate.get("evidenceStatus"),
            "absoluteElevationConstraintAuthorized":
                candidate.get("absoluteElevationConstraintAuthorized"),
            "independentSupportId": candidate.get("independentSupportId"),
            "constraintRole": candidate.get("constraintRole"),
            "controlId": control_id, "sourceId": candidate.get("sourceId"),
            "sourceArtifactSha256": digest,
        })
    audit = audit_surface_controls(controls)
    if not audit["passed"]:
        raise ValueError("reviewed controls fail the surface evidence gate")
    return {
        "schemaVersion": "ReviewedSurfaceControlGroup-1.0",
        "contactId": review["contactId"], "reviewId": review["reviewId"],
        "reviewerId": review["reviewerId"], "reviewedAt": review["reviewedAt"],
        "candidateRegistrySha256": review["candidateRegistrySha256"],
        "controls": controls, "evidenceAudit": audit,
        "automaticCorrelationUsed": False,
        "correlationBasis": "ExplicitArtifactBoundIndependentReview",
    }


def build_reviewed_route_contact_projection(
        candidate_registry: Mapping, review: Mapping, route_samples: Sequence[Mapping],
        *, shape_parameter, regularization, maximum_condition_number,
        maximum_control_residual_m) -> dict:
    """Run review -> evidence audit -> surface fit -> bounded route projection."""
    group = build_reviewed_surface_control_group(candidate_registry, review)
    surface = EvidenceBoundedRbfSurface(
        group["controls"], shape_parameter, regularization,
        maximum_condition_number=maximum_condition_number,
        maximum_control_residual_m=maximum_control_residual_m)
    projection = project_surface_to_route_samples(surface, route_samples)
    exact_coverage = intersect_route_with_evidence_hull(surface, route_samples)
    return {
        "schemaVersion": "ReviewedRouteContactProjection-1.0",
        "contactId": group["contactId"], "reviewId": group["reviewId"],
        "correlationBasis": group["correlationBasis"],
        "evidenceAudit": group["evidenceAudit"],
        "numericalAudit": surface.numerical_audit,
        "routeProjection": projection,
        "exactRouteCoverage": exact_coverage,
        "realRegionAuthorization": "RequiresExternalReleaseGate",
        "geometryBoundary": "OnlyInsideAuthorizedControlConvexHull",
    }
