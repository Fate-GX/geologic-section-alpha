import copy
import json
import unittest
from pathlib import Path

from geologic_3d_engine.validation.compaction_parameter_readiness import audit_compaction_parameter_readiness

ROOT = Path(__file__).resolve().parents[1]


class CompactionParameterReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads((ROOT / "examples" / "stage2_11_parameter_requirements_v1.json").read_text(encoding="utf-8"))
        cls.readiness = json.loads((ROOT / "examples" / "compaction_parameter_evidence_readiness_v1.json").read_text(encoding="utf-8"))

    def test_six_parameters_are_explicitly_unpromoted(self):
        result = audit_compaction_parameter_readiness(self.inventory, self.readiness)
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["parameterCount"], 6)
        self.assertEqual(result["syntheticAssumptionCount"], 6)
        self.assertEqual(result["realEvidenceBindingCount"], 0)
        self.assertFalse(result["realRegionAuthorized"])

    def test_equation_evidence_cannot_promote_a_fixture_value(self):
        mutated = copy.deepcopy(self.readiness)
        mutated["parameterAssessments"][0]["currentBasisType"] = "Literature"
        result = audit_compaction_parameter_readiness(self.inventory, mutated)
        self.assertIn("PrematureEvidencePromotion", {x["code"] for x in result["errors"]})

    def test_missing_parameter_is_rejected(self):
        mutated = copy.deepcopy(self.readiness)
        mutated["parameterAssessments"].pop()
        result = audit_compaction_parameter_readiness(self.inventory, mutated)
        self.assertIn("ReadinessCoverageMismatch", {x["code"] for x in result["errors"]})

    def test_duplicate_parameter_is_rejected(self):
        mutated = copy.deepcopy(self.readiness)
        mutated["parameterAssessments"].append(copy.deepcopy(mutated["parameterAssessments"][0]))
        result = audit_compaction_parameter_readiness(self.inventory, mutated)
        self.assertIn("ReadinessCoverageMismatch", {x["code"] for x in result["errors"]})

    def test_equation_support_must_remain_partial(self):
        mutated = copy.deepcopy(self.readiness)
        mutated["equationContract"]["sourceStatus"] = "Verified"
        result = audit_compaction_parameter_readiness(self.inventory, mutated)
        self.assertIn("EquationEvidenceOverclaim", {x["code"] for x in result["errors"]})

    def test_real_region_authorization_claim_is_rejected(self):
        mutated = copy.deepcopy(self.readiness)
        mutated["status"] = "RealRegionAuthorized"
        result = audit_compaction_parameter_readiness(self.inventory, mutated)
        self.assertIn("RealRegionAuthorizationOverclaim", {x["code"] for x in result["errors"]})


if __name__ == "__main__":
    unittest.main()
