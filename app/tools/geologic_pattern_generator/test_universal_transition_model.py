import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from universal_transition_model import fit_transition_model, leave_one_region_out, promotion_gate


class UniversalTransitionModelTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"regionId": "R1", "authorityId": "A1", "environment": "Fluvial",
             "process": "ChannelAbandonment", "sequence": ["gravel", "sand", "mud"]},
            {"regionId": "R2", "authorityId": "A2", "environment": "Fluvial",
             "process": "ChannelAbandonment", "sequence": ["gravel", "sand", "mud"]},
            {"regionId": "R3", "authorityId": "A1", "environment": "Fluvial",
             "process": "ChannelAbandonment", "sequence": ["gravel", "sand", "mud"]},
        ]

    def test_three_regions_two_authorities_can_be_cross_validated(self):
        model = fit_transition_model(self.records)
        validation = leave_one_region_out(self.records)
        self.assertTrue(validation["passedCoverage"])
        self.assertTrue(promotion_gate(model, validation)["promotable"])

    def test_local_single_region_cannot_set_prior(self):
        model = fit_transition_model(self.records[:1])
        validation = leave_one_region_out(self.records[:1])
        self.assertFalse(promotion_gate(model, validation)["promotable"])

    def test_environments_are_never_pooled(self):
        extra = dict(self.records[0])
        extra.update({"regionId": "R4", "environment": "Deltaic",
                      "process": "Progradation", "sequence": ["mud", "sand"]})
        model = fit_transition_model(self.records + [extra])
        self.assertEqual(len(model["models"]), 2)


if __name__ == "__main__":
    unittest.main()
