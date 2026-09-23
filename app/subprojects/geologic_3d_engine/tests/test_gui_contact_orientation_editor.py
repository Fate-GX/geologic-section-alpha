import unittest

from geologic_3d_engine.gui_contact_orientation_editor import update_hypothesis_row
from tests.test_contact_orientation_hypothesis import intersections
from geologic_3d_engine.section.contact_orientation_hypothesis import (
    build_contact_orientation_hypothesis_template,
    evaluate_contact_orientation_hypotheses)


class ContactOrientationEditorBackendTests(unittest.TestCase):
    def test_synthetic_and_evidence_candidate_edits_are_hash_valid(self):
        template=build_contact_orientation_hypothesis_template(intersections())
        result=update_hypothesis_row(template,0,{"orientationBasis":"SyntheticAssumption",
            "trueDipDegrees":"25","dipDirectionDegrees":"135",
            "angularUncertaintyDegrees":"3","lateralSupportM":"250",
            "basisSourceIds":"","interpretationNote":"hypothesis"})
        self.assertEqual(evaluate_contact_orientation_hypotheses(result,{0:90})["evaluatedCount"],1)
        result=update_hypothesis_row(template,0,{"orientationBasis":"EvidenceCandidate",
            "trueDipDegrees":10,"dipDirectionDegrees":0,
            "angularUncertaintyDegrees":1,"lateralSupportM":100,
            "basisSourceIds":"SRC-1, SRC-2","interpretationNote":"candidate"})
        self.assertEqual(result["hypotheses"][0]["basisSourceIds"],["SRC-1","SRC-2"])

    def test_missing_source_invalid_angle_and_reset_reject_or_clear(self):
        template=build_contact_orientation_hypothesis_template(intersections())
        common={"orientationBasis":"EvidenceCandidate","trueDipDegrees":10,
            "dipDirectionDegrees":0,"angularUncertaintyDegrees":1,"lateralSupportM":100,
            "basisSourceIds":"","interpretationNote":""}
        with self.assertRaises(ValueError):update_hypothesis_row(template,0,common)
        with self.assertRaises(ValueError):update_hypothesis_row(template,0,{**common,
            "orientationBasis":"SyntheticAssumption","trueDipDegrees":88,
            "angularUncertaintyDegrees":3})
        filled=update_hypothesis_row(template,0,{**common,"orientationBasis":"SyntheticAssumption"})
        cleared=update_hypothesis_row(filled,0,{"orientationBasis":"NeedsInput"})
        self.assertIsNone(cleared["hypotheses"][0]["trueDipDegrees"])
        self.assertFalse(cleared["hypotheses"][0]["subsurfaceContinuationAuthorized"])


if __name__=="__main__":unittest.main()
