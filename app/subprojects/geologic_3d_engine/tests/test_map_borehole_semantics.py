import unittest

from geologic_3d_engine.section.map_borehole_semantics import compare_mapped_geology_to_borehole


class MapBoreholeSemanticTests(unittest.TestCase):
    def setUp(self):
        self.map = {"sourceId": "MAP", "matches": [{"symbol": "a"}]}
        self.hole = {"sourceId": "CORE", "intervals": [
            {"topDepthM": 0, "bottomDepthM": 4.46, "sourceLabel": "降下火山灰"},
            {"topDepthM": 4.46, "bottomDepthM": 9, "sourceLabel": "降下スコリア"}]}

    def test_text_resemblance_never_auto_binds(self):
        result = compare_mapped_geology_to_borehole(self.map, self.hole)
        self.assertEqual(result["status"], "NeedsReviewedLithologyBinding")
        self.assertFalse(result["thicknessAuthorized"])

    def test_reviewed_binding_preserves_boundary(self):
        binding = {"mapSourceId": "MAP", "boreholeSourceId": "CORE",
                   "intervalIndex": 0,
                   "relation": "CompatibleAtDifferentRepresentationDepth",
                   "reviewStatus": "IndependentlyReviewed"}
        result = compare_mapped_geology_to_borehole(self.map, self.hole,
                                                     reviewed_binding=binding)
        self.assertEqual(result["selectedInterval"]["bottomDepthM"], 4.46)
        self.assertFalse(result["contactGeometryAuthorized"])

    def test_wrong_source_and_unreviewed_are_safe(self):
        binding = {"mapSourceId": "OTHER", "boreholeSourceId": "CORE",
                   "intervalIndex": 0, "relation": "Unresolved",
                   "reviewStatus": "IndependentlyReviewed"}
        with self.assertRaises(ValueError):
            compare_mapped_geology_to_borehole(self.map, self.hole,
                                                reviewed_binding=binding)
        binding["mapSourceId"] = "MAP"
        binding["reviewStatus"] = "Pending"
        self.assertEqual(compare_mapped_geology_to_borehole(
            self.map, self.hole, reviewed_binding=binding)["status"],
            "NeedsIndependentReview")

    def test_cover_category_does_not_authorize_identity_or_geometry(self):
        binding = {"mapSourceId": "MAP", "boreholeSourceId": "CORE",
                   "intervalIndex": 0,
                   "relation": "CompatibleCoverCategory_NotStratigraphicIdentity",
                   "reviewStatus": "IndependentlyReviewed"}
        result = compare_mapped_geology_to_borehole(
            self.map, self.hole, reviewed_binding=binding)
        self.assertEqual(result["status"], binding["relation"])
        self.assertFalse(result["subsurfaceContinuationAuthorized"])
        self.assertFalse(result["thicknessAuthorized"])


if __name__ == "__main__":
    unittest.main()
