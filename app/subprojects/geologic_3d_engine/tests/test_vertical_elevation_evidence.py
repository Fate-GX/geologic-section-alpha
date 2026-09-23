import unittest

from geologic_3d_engine.section.vertical_elevation_evidence import (
    build_reported_elevation_envelope, translate_depth_to_elevation_envelope)


def observation(source, value, resolution, digest="a"*64):
    return {"sourceId": source, "sourceUrl": f"https://example.invalid/{source}",
            "valueM": value, "reportingResolutionM": resolution,
            "sourceArtifactSha256": digest}


class VerticalElevationEvidenceTests(unittest.TestCase):
    def test_compatible_rounding_is_not_promoted_to_accuracy(self):
        result = build_reported_elevation_envelope([
            observation("CORE", 1142.6, 0.1), observation("STATION", 1143.0, 1.0)],
            vertical_datum="TokyoBayMeanSeaLevel_JapanHeightDatum")
        self.assertEqual(result["roundingIntersectionM"], [1142.55, 1142.6499999999999])
        self.assertEqual(result["consistencyStatus"],
                         "NumericallyConsistent_NotAccuracyEvidence")
        self.assertFalse(result["sectionConstraintAuthorized"])
        translated = translate_depth_to_elevation_envelope(result, [0, 100])
        self.assertEqual(translated[1]["elevationEnvelopeM"],
                         [1042.55, 1042.6499999999999])
        self.assertFalse(translated[1]["sectionConstraintAuthorized"])

    def test_conflict_bad_hash_and_negative_depth_reject(self):
        conflict = build_reported_elevation_envelope([
            observation("A", 100, 0.1), observation("B", 102, 0.1)],
            vertical_datum="TP")
        self.assertEqual(conflict["consistencyStatus"], "ConflictingPublishedElevations")
        with self.assertRaises(ValueError):
            translate_depth_to_elevation_envelope(conflict, [1])
        with self.assertRaises(ValueError):
            build_reported_elevation_envelope([observation("A", 1, 1, "X"*64),
                                               observation("B", 1, 1)], vertical_datum="TP")
        valid = build_reported_elevation_envelope([observation("A", 1, 1),
                                                   observation("B", 1, 1)], vertical_datum="TP")
        with self.assertRaises(ValueError):
            translate_depth_to_elevation_envelope(valid, [-1])


if __name__ == "__main__":
    unittest.main()
