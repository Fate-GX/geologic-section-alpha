import copy
import pathlib
import sys
import unittest

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from geologic_3d_engine.export.authenticated_validation import (
    build_authenticated_validation, verify_authenticated_validation)
from geologic_3d_engine.export.contract_integrity import build_integrity_envelope

KEY = b"synthetic-test-key-not-for-production-0001"
OTHER_KEY = b"synthetic-test-key-not-for-production-0002"
PURPOSE = "stochastic-thickness-upstream-validation"


def artifact(**overrides):
    values = {
        "integrity_envelope": build_integrity_envelope(
            {"requestId": "R1"}, {"passed": True}, "fixture-validator"),
        "secret": KEY, "key_id": "test-key-1", "purpose": PURPOSE,
        "issued_at_utc": "2026-08-30T10:00:00Z",
        "expires_at_utc": "2026-08-30T10:05:00Z",
        "nonce": "0123456789abcdef0123456789abcdef",
    }
    values.update(overrides)
    return build_authenticated_validation(**values)


def verify(value, *, now="2026-08-30T10:01:00Z", keys=None, nonces=None,
           purpose=PURPOSE):
    return verify_authenticated_validation(
        value, trusted_keys=keys or {"test-key-1": KEY}, expected_purpose=purpose,
        now_utc=now, used_nonces=nonces if nonces is not None else set())


class AuthenticatedValidationTests(unittest.TestCase):
    def test_positive_valid_artifact(self):
        self.assertIn("payloadSha256", verify(artifact()))

    def test_negative_wrong_key_rejects_mac(self):
        with self.assertRaisesRegex(ValueError, "MAC mismatch"):
            verify(artifact(), keys={"test-key-1": OTHER_KEY})

    def test_boundary_exact_expiry_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "expired"):
            verify(artifact(), now="2026-08-30T10:05:00Z")

    def test_conflicting_purpose_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "purpose mismatch"):
            verify(artifact(), purpose="different-purpose")

    def test_missing_mac_is_rejected(self):
        value = artifact(); del value["macHex"]
        with self.assertRaisesRegex(ValueError, "missing"):
            verify(value)

    def test_out_of_scope_algorithm_is_rejected(self):
        value = artifact(); value["algorithm"] = "Ed25519"
        with self.assertRaisesRegex(ValueError, "algorithm"):
            verify(value)

    def test_payload_tamper_is_rejected(self):
        value = artifact(); value["integrityEnvelope"]["payloadSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "MAC mismatch"):
            verify(value)

    def test_nonce_replay_is_rejected(self):
        nonces = set(); value = artifact()
        verify(value, nonces=nonces)
        with self.assertRaisesRegex(ValueError, "replay"):
            verify(value, nonces=nonces)

    def test_unknown_key_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown or revoked"):
            verify(artifact(), keys={"another-key": KEY})

    def test_overlong_lifetime_is_rejected(self):
        value = artifact(expires_at_utc="2026-08-30T11:00:00Z")
        with self.assertRaisesRegex(ValueError, "lifetime exceeds"):
            verify(value)

    def test_future_issue_outside_skew_is_rejected(self):
        value = artifact(issued_at_utc="2026-08-30T10:02:00Z",
                         expires_at_utc="2026-08-30T10:03:00Z")
        with self.assertRaisesRegex(ValueError, "future"):
            verify(value, now="2026-08-30T10:00:00Z")


if __name__ == "__main__":
    unittest.main()
