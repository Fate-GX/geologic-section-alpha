import copy
import json
import unittest
from pathlib import Path

from geologic_3d_engine.profiles.compaction_parameter_evidence import validate_compaction_evidence_candidates

ROOT = Path(__file__).resolve().parents[1]


class CompactionParameterEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inventory = json.loads((ROOT / "examples" / "stage2_11_parameter_requirements_v1.json").read_text(encoding="utf-8"))
        cls.requirements = inventory["requirements"]
        cls.profile_id = inventory["profileId"]
        cls.fixture = json.loads((ROOT / "examples" / "compaction_parameter_candidate_contract_fixture_v1.json").read_text(encoding="utf-8"))

    def candidates(self):
        template = self.fixture["candidateTemplate"]
        output = []
        for requirement in self.requirements:
            if not requirement["parameterId"].startswith("S6-COMP-"):
                continue
            item = copy.deepcopy(template)
            item.update({
                "parameterId": requirement["parameterId"],
                "profileId": self.profile_id,
                "implementationPath": requirement["implementationPath"],
                "value": requirement["value"],
                "unitIdentity": requirement["parameterId"].split("-")[2],
                "normalizedTerminology": "Synthetic unit",
                "state": "sourcePorosity" if requirement["parameterId"].endswith("SOURCE") else "targetPorosity",
            })
            output.append(item)
        return output

    def validate(self, candidates):
        return validate_compaction_evidence_candidates(
            self.requirements, candidates, self.fixture["declaredSourceIds"], self.profile_id
        )

    def test_structurally_complete_pending_candidates_do_not_authorize_region(self):
        result = self.validate(self.candidates())
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["structurallyValidCount"], 6)
        self.assertEqual(result["independentlyVerifiedCount"], 0)
        self.assertFalse(result["realRegionAuthorized"])

    def test_self_declared_verified_hashes_cannot_authorize(self):
        candidates = self.candidates()
        for item in candidates:
            item["semanticReviewStatus"] = "IndependentlyVerified"
            item["artifactSha256"] = "a" * 64
        result = self.validate(candidates)
        self.assertFalse(result["passed"])
        self.assertFalse(result["realRegionAuthorized"])
        self.assertEqual(result["integrityBoundCount"], 0)

    def test_verified_without_artifact_hash_rejects(self):
        candidates = self.candidates()
        candidates[0]["semanticReviewStatus"] = "IndependentlyVerified"
        result = self.validate(candidates)
        self.assertIn("VerifiedCandidateArtifactHashMissing", {x["code"] for x in result["errors"]})

    def test_synthetic_assumption_is_not_real_candidate_basis(self):
        candidates = self.candidates(); candidates[0]["basisType"] = "SyntheticAssumption"
        self.assertIn("CandidateBasisNotRealEvidence", {x["code"] for x in self.validate(candidates)["errors"]})

    def test_measurement_definition_is_mandatory(self):
        candidates = self.candidates(); candidates[0]["measurement"].pop("porosityDefinition")
        self.assertIn("CandidateMeasurementDefinitionMissing", {x["code"] for x in self.validate(candidates)["errors"]})

    def test_burial_context_is_mandatory(self):
        candidates = self.candidates(); candidates[0]["burialContext"].pop("depthDatum")
        self.assertIn("CandidateBurialContextMissing", {x["code"] for x in self.validate(candidates)["errors"]})

    def test_exact_locator_is_mandatory(self):
        candidates = self.candidates(); candidates[0]["sourceLocator"]["locatorStatus"] = "CatalogEntryOnly"
        self.assertIn("CandidateSourceLocatorInvalid", {x["code"] for x in self.validate(candidates)["errors"]})

    def test_duplicate_record_is_rejected(self):
        candidates = self.candidates(); candidates.append(copy.deepcopy(candidates[0]))
        self.assertIn("CandidateCoverageMismatch", {x["code"] for x in self.validate(candidates)["errors"]})


if __name__ == "__main__":
    unittest.main()
