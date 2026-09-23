"""All evidence bytes and reviewer identities here are synthetic test data."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tests import test_compaction_parameter_evidence as fixture_tests
from geologic_3d_engine.profiles.compaction_parameter_evidence import (
    candidate_binding_sha256, validate_compaction_evidence_candidates,
)


class EvidenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        fixture_tests.CompactionParameterEvidenceTests.setUpClass()
        fixture = fixture_tests.CompactionParameterEvidenceTests()
        self.requirements = fixture.requirements
        self.profile = fixture.profile_id
        self.sources = fixture.fixture["declaredSourceIds"]
        self.candidates = fixture.candidates()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pins = {}
        (self.root / "evidence.txt").write_bytes(b"Synthetic contract-test evidence, not geology")
        for index, item in enumerate(self.candidates):
            item.update(semanticReviewStatus="IndependentlyVerified", artifactPath="evidence.txt",
                        artifactSha256=hashlib.sha256((self.root / "evidence.txt").read_bytes()).hexdigest(),
                        reviewPath=f"review-{index}.json")
            self.write_review(item)

    def write_review(self, item, **changes):
        record = {"recordKind": "RealEvidenceReview", "decision": "SupportsCandidate",
                  "reviewerId": "SIMULATED-REVIEWER-NOT-A-REAL-REVIEW",
                  "bindingVersion": "CandidateEvidenceBinding-1",
                  "candidateSha256": candidate_binding_sha256(item)}
        record.update(changes)
        content = json.dumps(record).encode()
        (self.root / item["reviewPath"]).write_bytes(content)
        self.pins[item["parameterId"]] = hashlib.sha256(content).hexdigest()

    def run_gate(self):
        return validate_compaction_evidence_candidates(
            self.requirements, self.candidates, self.sources, self.profile,
            artifact_root=self.root, trusted_review_hashes=self.pins)

    def assert_rejected(self):
        result = self.run_gate()
        self.assertFalse(result["passed"], result)
        self.assertFalse(result["realRegionAuthorized"])

    def test_matching_files_and_trusted_pins_only_establish_integrity(self):
        result = self.run_gate()
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["integrityBoundCount"], 6)
        self.assertEqual(result["independentlyVerifiedCount"], 0)
        self.assertFalse(result["realRegionAuthorized"])

    def test_evidence_tampering(self):
        (self.root / "evidence.txt").write_bytes(b"changed")
        self.assert_rejected()

    def test_missing_evidence(self):
        self.candidates[0]["artifactPath"] = "absent.txt"
        self.assert_rejected()

    def test_review_tampering(self):
        (self.root / "review-0.json").write_bytes(b"{}")
        self.assert_rejected()

    def test_missing_trust_pin(self):
        self.pins.clear()
        self.assert_rejected()

    def test_changed_value_invalidates_pinned_review(self):
        self.assertTrue(self.run_gate()["passed"])
        before_pins = dict(self.pins)
        before_review = (self.root / "review-0.json").read_bytes()
        self.candidates[0]["value"] = 0.45
        result = self.run_gate()
        self.assertFalse(result["passed"])
        self.assertEqual(result["errors"], [{
            "code": "CandidateEvidenceBindingRejected",
            "parameterId": self.candidates[0]["parameterId"],
            "reason": "Review candidate binding mismatch",
        }])
        self.assertEqual(self.pins, before_pins)
        self.assertEqual((self.root / "review-0.json").read_bytes(), before_review)
        self.assertFalse(result["realRegionAuthorized"])

    def test_changed_source_or_scope_or_state_invalidates_review(self):
        original = copy.deepcopy(self.candidates)
        for key in ("sourceLocator", "applicability", "state", "measurement"):
            with self.subTest(key=key):
                self.candidates = copy.deepcopy(original)
                if key == "state":
                    self.candidates[0][key] = "targetPorosity"
                else:
                    self.candidates[0][key]["additionalContext"] = "changed after review"
                self.assert_rejected()

    def test_synthetic_review_rejected_even_when_pinned(self):
        self.write_review(self.candidates[0], recordKind="SyntheticContractFixture")
        self.assert_rejected()

    def test_conflicting_review_rejected_even_when_pinned(self):
        self.write_review(self.candidates[0], decision="RejectCandidate")
        self.assert_rejected()

    def test_path_escape_rejected(self):
        self.candidates[0]["artifactPath"] = "../outside.txt"
        self.assert_rejected()

    def test_recomputed_artifact_hash_does_not_refresh_review(self):
        (self.root / "evidence.txt").write_bytes(b"changed")
        for item in self.candidates:
            item["artifactSha256"] = hashlib.sha256(b"changed").hexdigest()
        self.assert_rejected()

    def test_duplicate_rejected(self):
        self.candidates.append(copy.deepcopy(self.candidates[0]))
        self.assert_rejected()


if __name__ == "__main__":
    unittest.main()
