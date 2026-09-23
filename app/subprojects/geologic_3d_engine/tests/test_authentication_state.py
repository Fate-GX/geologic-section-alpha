import pathlib
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from geologic_3d_engine.export.authenticated_validation import build_authenticated_validation
from geologic_3d_engine.export.authentication_state import (
    SqliteNonceStore, signing_key, validate_key_policies, verification_key,
    verify_with_rotation_policy)
from geologic_3d_engine.export.contract_integrity import build_integrity_envelope

PURPOSE = "stochastic-thickness-upstream-validation"
OLD = b"synthetic-old-key-not-for-production-00001"
NEW = b"synthetic-new-key-not-for-production-00001"


def policies():
    return validate_key_policies([
        {"keyId": "old", "status": "VerifyOnly", "notBeforeUtc": "2026-01-01T00:00:00Z",
         "notAfterUtc": "2027-01-01T00:00:00Z", "purposes": [PURPOSE]},
        {"keyId": "new", "status": "Active", "notBeforeUtc": "2026-08-01T00:00:00Z",
         "notAfterUtc": "2027-08-01T00:00:00Z", "purposes": [PURPOSE]},
        {"keyId": "bad", "status": "Revoked", "notBeforeUtc": "2026-01-01T00:00:00Z",
         "notAfterUtc": "2027-01-01T00:00:00Z", "purposes": [PURPOSE]},
    ])


def artifact(key_id="new", secret=NEW, nonce="0123456789abcdef0123456789abcdef"):
    integrity = build_integrity_envelope({"id": "R1"}, {"passed": True}, "validator")
    return build_authenticated_validation(
        integrity, secret=secret, key_id=key_id, purpose=PURPOSE,
        issued_at_utc="2026-08-30T10:00:00Z", expires_at_utc="2026-08-30T10:05:00Z",
        nonce=nonce)


class AuthenticationStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.temp.name) / "nonces.sqlite3"
        self.secrets = {"old": OLD, "new": NEW, "bad": NEW}
        self.policies = policies()

    def tearDown(self): self.temp.cleanup()

    def test_positive_active_key_and_persistent_nonce(self):
        verify_with_rotation_policy(
            artifact(), secrets=self.secrets, policies=self.policies, expected_purpose=PURPOSE,
            now_utc="2026-08-30T10:01:00Z", nonce_store=SqliteNonceStore(self.path))
        with self.assertRaisesRegex(ValueError, "replay"):
            verify_with_rotation_policy(
                artifact(), secrets=self.secrets, policies=self.policies,
                expected_purpose=PURPOSE, now_utc="2026-08-30T10:01:00Z",
                nonce_store=SqliteNonceStore(self.path))

    def test_negative_revoked_key_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "revoked"):
            verification_key(key_id="bad", purpose=PURPOSE, now_utc="2026-08-30T10:01:00Z",
                             secrets=self.secrets, policies=self.policies)

    def test_boundary_not_after_is_exclusive(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            verification_key(key_id="old", purpose=PURPOSE, now_utc="2027-01-01T00:00:00Z",
                             secrets=self.secrets, policies=self.policies)

    def test_conflicting_duplicate_key_id_is_rejected(self):
        duplicate = [dict(self.policies["new"]), dict(self.policies["new"])]
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_key_policies(duplicate)

    def test_missing_secret_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "both policy"):
            verification_key(key_id="new", purpose=PURPOSE, now_utc="2026-08-30T10:01:00Z",
                             secrets={}, policies=self.policies)

    def test_out_of_scope_purpose_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "purpose"):
            verification_key(key_id="new", purpose="other", now_utc="2026-08-30T10:01:00Z",
                             secrets=self.secrets, policies=self.policies)

    def test_verify_only_key_can_verify_but_cannot_sign(self):
        self.assertEqual(verification_key(
            key_id="old", purpose=PURPOSE, now_utc="2026-08-30T10:01:00Z",
            secrets=self.secrets, policies=self.policies), OLD)
        with self.assertRaisesRegex(ValueError, "Active"):
            signing_key(key_id="old", purpose=PURPOSE, now_utc="2026-08-30T10:01:00Z",
                        secrets=self.secrets, policies=self.policies)

    def test_prune_removes_only_expired_rows(self):
        store = SqliteNonceStore(self.path)
        self.assertTrue(store.consume("old", "a" * 32, "2026-08-30T10:02:00Z",
                                      "2026-08-30T10:01:00Z"))
        self.assertTrue(store.consume("new", "b" * 32, "2026-08-30T10:10:00Z",
                                      "2026-08-30T10:01:00Z"))
        self.assertEqual(store.prune_expired("2026-08-30T10:05:00Z"), 1)
        self.assertTrue(store.consume("old", "a" * 32, "2026-08-30T10:06:00Z",
                                      "2026-08-30T10:05:00Z"))

    def test_concurrent_nonce_consumption_has_one_winner(self):
        store = SqliteNonceStore(self.path)
        def consume_once(_):
            return store.consume(
                "new", "c" * 32, "2026-08-30T10:10:00Z", "2026-08-30T10:01:00Z")
        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes = list(executor.map(consume_once, range(16)))
        self.assertEqual(outcomes.count(True), 1)
        self.assertEqual(outcomes.count(False), 15)


if __name__ == "__main__": unittest.main()
