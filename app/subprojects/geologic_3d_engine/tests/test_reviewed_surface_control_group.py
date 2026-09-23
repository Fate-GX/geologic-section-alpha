import copy
import unittest

from geologic_3d_engine.section.reviewed_surface_control_group import (
    build_reviewed_route_contact_projection, build_reviewed_surface_control_group,
    canonical_sha256)


def registry():
    points = []
    for index, (x, y, z) in enumerate(((0, 0, 10), (10, 0, 12), (0, 10, 7))):
        points.append({"controlId": f"P{index}", "xM": x, "yM": y, "zM": z,
                       "sourceId": f"SOURCE-{index}",
                       "sourceArtifactSha256": chr(97 + index) * 64,
                       "evidenceStatus": "Observed",
                       "absoluteElevationConstraintAuthorized": True,
                       "independentSupportId": f"BH-{index}",
                       "constraintRole": "DirectSubsurfaceContact"})
    return {"schemaVersion": "SurfaceControlCandidateRegistry-1.0",
            "horizontalCrs": "EPSG:6670", "verticalDatum": "TP", "candidates": points}


def review(data):
    return {"schemaVersion": "SurfaceControlCorrelationReview-1.0",
            "reviewId": "R1", "reviewerId": "GEOLOGIST-1",
            "reviewedAt": "2026-09-05T00:00:00Z",
            "reviewStatus": "IndependentlyReviewed",
            "candidateRegistrySha256": canonical_sha256(data),
            "contactId": "CONTACT-A", "selectedControlIds": ["P0", "P1", "P2"]}


class ReviewedSurfaceControlGroupTests(unittest.TestCase):
    def test_explicit_bound_review_builds_ready_controls(self):
        data = registry(); result = build_reviewed_surface_control_group(data, review(data))
        self.assertTrue(result["evidenceAudit"]["passed"])
        self.assertFalse(result["automaticCorrelationUsed"])
        self.assertEqual(result["evidenceAudit"]["independentSupportCount"], 3)

    def test_equal_labels_or_depths_never_select_themselves(self):
        data = registry()
        for item in data["candidates"]:
            item.update(normalizedLithology="ash", depthM=4.46)
        draft = review(data); draft["reviewStatus"] = "Draft_NotReviewed"
        with self.assertRaises(ValueError):
            build_reviewed_surface_control_group(data, draft)

    def test_tampering_unknown_duplicate_and_bad_hash_reject(self):
        data = registry(); binding = review(data)
        changed = copy.deepcopy(data); changed["candidates"][0]["zM"] += 1
        with self.assertRaises(ValueError):
            build_reviewed_surface_control_group(changed, binding)
        unknown = review(data); unknown["selectedControlIds"][2] = "MISSING"
        with self.assertRaises(ValueError):
            build_reviewed_surface_control_group(data, unknown)
        duplicate = review(data); duplicate["selectedControlIds"][2] = "P1"
        with self.assertRaises(ValueError):
            build_reviewed_surface_control_group(data, duplicate)
        bad = registry(); bad["candidates"][0]["sourceArtifactSha256"] = "X" * 64
        with self.assertRaises(ValueError):
            build_reviewed_surface_control_group(bad, review(bad))

    def test_same_borehole_repeated_cannot_fake_independence(self):
        data = registry()
        for item in data["candidates"]:
            item["independentSupportId"] = "ONE-HOLE"
        with self.assertRaises(ValueError):
            build_reviewed_surface_control_group(data, review(data))

    def test_end_to_end_review_surface_and_route_projection(self):
        data = registry()
        route = [{"stationM": i * 10, "xM": x, "yM": 2}
                 for i, x in enumerate((-2, 0, 2, 4, 6, 8, 10))]
        result = build_reviewed_route_contact_projection(
            data, review(data), route, shape_parameter=.4, regularization=0,
            maximum_condition_number=1e12, maximum_control_residual_m=1e-9)
        self.assertTrue(result["evidenceAudit"]["passed"])
        self.assertTrue(result["numericalAudit"]["passed"])
        self.assertEqual(result["routeProjection"]["supportedSampleCount"], 5)
        self.assertEqual(result["exactRouteCoverage"]["supportedIntervalCount"], 1)
        self.assertFalse(result["exactRouteCoverage"]["sampleSpacingDependency"])
        self.assertEqual(result["realRegionAuthorization"],
                         "RequiresExternalReleaseGate")


if __name__ == "__main__":
    unittest.main()
