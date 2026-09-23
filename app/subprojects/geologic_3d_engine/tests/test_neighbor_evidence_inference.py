import unittest

from geologic_3d_engine.profiles.neighbor_evidence_inference import infer_from_neighboring_evidence


class NeighborEvidenceInferenceTests(unittest.TestCase):
    def setUp(self):
        self.target = {"targetId": "T", "geologicalProvince": "P",
                       "ageInterval": "Q", "environment": "Alluvial"}

    def row(self, source, distance, lithologies, **changes):
        value = {"sourceId": source, "distanceM": distance, "lithologies": lithologies,
                 "geologicalProvince": "P", "ageInterval": "Q",
                 "environment": "Alluvial", "evidenceStatus": "Observed"}
        value.update(changes)
        return value

    def test_selects_compatible_neighbors_and_discloses_inference(self):
        result = infer_from_neighboring_evidence(self.target, [
            self.row("NEAR", 1200, ["砂", "泥"]), self.row("FAR", 8000, ["泥", "礫"])])
        self.assertTrue(result["passed"])
        self.assertEqual(result["basisType"], "InferredFromNeighboringRegionalEvidence")
        self.assertEqual(result["inferredLithologies"][0], "泥")
        self.assertIn("周辺地域", result["drawingDisclosureJa"])
        self.assertFalse(result["directTargetEvidence"])
        self.assertFalse(result["realRegionAuthorized"])

    def test_distance_and_geological_context_are_both_gates(self):
        result = infer_from_neighboring_evidence(self.target, [
            self.row("TOO-FAR", 50001, ["砂"]),
            self.row("WRONG-PROVINCE", 100, ["花崗岩"], geologicalProvince="X")])
        self.assertFalse(result["passed"])
        self.assertEqual({x["reason"] for x in result["rejectedCandidates"]},
                         {"OutsideSupportDistance", "GeologicalApplicabilityMismatch"})

    def test_unreviewed_claim_is_not_accepted(self):
        result = infer_from_neighboring_evidence(self.target, [
            self.row("CLAIM", 50, ["砂"], evidenceStatus="SyntheticAssumption")])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
