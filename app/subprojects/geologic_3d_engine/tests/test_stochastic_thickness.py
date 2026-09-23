import pathlib
import sys
import tempfile
import time
import unittest
from unittest import mock

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from geologic_3d_engine.export.authenticated_validation import build_authenticated_validation
from geologic_3d_engine.export.authentication_state import SqliteNonceStore, validate_key_policies
from geologic_3d_engine.export.contract_integrity import build_integrity_envelope
from geologic_3d_engine.fields.stochastic_thickness import (
    ALGORITHM_VERSION, AUTHENTICATION_PURPOSE, UPSTREAM_VALIDATION_KIND,
    UPSTREAM_VALIDATOR_VERSION, generate_stochastic_thickness)

KEY = b"stochastic-generator-test-key-not-production-01"
NOW = "2026-08-30T10:01:00Z"


def unsigned_request():
    return {"contractVersion": "0.8.0-candidate", "algorithmVersion": ALGORITHM_VERSION,
            "randomSeed": 1234, "grid": {"nx": 3, "ny": 2, "spacingX": 10, "spacingY": 10},
            "psdAudit": {"symmetryTolerance": 1e-12, "absoluteEigenTolerance": 1e-12,
                         "relativeEigenTolerance": 1e-12, "toleranceJustification": "test matrix"},
            "layers": [{"unitId": "U1", "threshold": 0.0,
                        "transform": {"kind": "PowerPositivePart", "mu": 10.0, "beta": 1.5},
                        "crossLayerPolicy": "Independent",
                        "withinLayerCovariance": {"model": "Gaussian", "variance": 1.0,
                                                  "ranges": [20.0, 10.0]},
                        "parameterEvidenceIds": ["SYNTHETIC-TEST-EVIDENCE"]}]}


class StochasticThicknessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.counter = 0
        self.policies = validate_key_policies([{
            "keyId": "generator-key", "status": "Active",
            "notBeforeUtc": "2026-01-01T00:00:00Z", "notAfterUtc": "2027-01-01T00:00:00Z",
            "purposes": [AUTHENTICATION_PURPOSE]}])

    def tearDown(self): self.temp.cleanup()

    def authorize(self, payload, *, passed=True, kind=UPSTREAM_VALIDATION_KIND):
        self.counter += 1
        integrity = build_integrity_envelope(
            payload, {"passed": passed, "contractVersion": "0.8.0-candidate",
                      "validationKind": kind}, UPSTREAM_VALIDATOR_VERSION)
        authenticated = build_authenticated_validation(
            integrity, secret=KEY, key_id="generator-key", purpose=AUTHENTICATION_PURPOSE,
            issued_at_utc="2026-08-30T10:00:00Z", expires_at_utc="2026-08-30T10:05:00Z",
            nonce=f"{self.counter:032x}")
        request = dict(payload); request["authenticatedUpstreamValidation"] = authenticated
        context = {"secrets": {"generator-key": KEY}, "policies": self.policies,
                   "nowUtc": NOW, "nonceStore": SqliteNonceStore(
                       pathlib.Path(self.temp.name) / "nonces.sqlite3")}
        return request, context

    def generate(self, payload):
        request, context = self.authorize(payload)
        return generate_stochastic_thickness(request, authentication_context=context)

    def test_seeded_replay_is_exact_with_distinct_authorizations(self):
        self.assertEqual(self.generate(unsigned_request()), self.generate(unsigned_request()))

    def test_different_seed_changes_payload(self):
        first = unsigned_request(); other = unsigned_request(); other["randomSeed"] = 1235
        self.assertNotEqual(self.generate(first)["payloadSha256"], self.generate(other)["payloadSha256"])

    def test_thickness_is_non_negative_and_psd_passes(self):
        result = self.generate(unsigned_request())["layers"][0]
        self.assertGreaterEqual(result["minimumThickness"], 0); self.assertTrue(result["psdAudit"]["passed"])

    def test_high_threshold_produces_explicit_zero_thickness(self):
        data = unsigned_request(); data["layers"][0]["threshold"] = 1e6
        self.assertEqual(self.generate(data)["layers"][0]["zeroThicknessCount"], 6)

    def test_authentication_is_required_before_generation(self):
        with self.assertRaisesRegex(ValueError, "authenticated upstream"):
            generate_stochastic_thickness(unsigned_request(), authentication_context={})

    def test_bound_request_mutation_rejected_without_consuming_nonce(self):
        request, context = self.authorize(unsigned_request()); request["randomSeed"] = 999
        with self.assertRaisesRegex(ValueError, "different request"):
            generate_stochastic_thickness(request, authentication_context=context)
        request["randomSeed"] = 1234
        self.assertEqual(generate_stochastic_thickness(request, authentication_context=context)["randomSeed"], 1234)

    def test_hmac_failure_does_not_consume_nonce(self):
        request, context = self.authorize(unsigned_request())
        original = request["authenticatedUpstreamValidation"]["integrityEnvelope"]["payloadSha256"]
        request["authenticatedUpstreamValidation"]["integrityEnvelope"]["payloadSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "MAC mismatch"):
            generate_stochastic_thickness(request, authentication_context=context)
        request["authenticatedUpstreamValidation"]["integrityEnvelope"]["payloadSha256"] = original
        self.assertEqual(generate_stochastic_thickness(request, authentication_context=context)["randomSeed"], 1234)

    def test_auth_failure_occurs_before_numerical_sampling(self):
        request, context = self.authorize(unsigned_request()); request["randomSeed"] = 999
        with mock.patch("geologic_3d_engine.fields.stochastic_thickness.np.linalg.eigh",
                        side_effect=AssertionError("numerical sampling was reached")):
            with self.assertRaisesRegex(ValueError, "different request"):
                generate_stochastic_thickness(request, authentication_context=context)

    def test_replay_is_rejected(self):
        request, context = self.authorize(unsigned_request())
        generate_stochastic_thickness(request, authentication_context=context)
        with self.assertRaisesRegex(ValueError, "replay"):
            generate_stochastic_thickness(request, authentication_context=context)

    def test_failed_validation_is_rejected(self):
        request, context = self.authorize(unsigned_request(), passed=False)
        with self.assertRaisesRegex(ValueError, "did not pass"):
            generate_stochastic_thickness(request, authentication_context=context)

    def test_wrong_validation_kind_is_rejected(self):
        request, context = self.authorize(unsigned_request(), kind="OtherGate")
        with self.assertRaisesRegex(ValueError, "validationKind mismatch"):
            generate_stochastic_thickness(request, authentication_context=context)

    def test_geological_input_rejection_occurs_after_authentication(self):
        data = unsigned_request(); data["layers"][0]["crossLayerPolicy"] = "Correlated"
        request, context = self.authorize(data)
        with self.assertRaisesRegex(ValueError, "independent"):
            generate_stochastic_thickness(request, authentication_context=context)

    def test_generator_does_not_materialize_kronecker_full_matrix(self):
        with mock.patch("numpy.kron", side_effect=AssertionError("full matrix materialized")):
            result = self.generate(unsigned_request())
        self.assertFalse(result["layers"][0]["psdAudit"]["fullMatrixMaterialized"])

    def test_100_by_100_completes_on_separable_path(self):
        data = unsigned_request(); data["grid"].update({"nx": 100, "ny": 100})
        started = time.perf_counter(); result = self.generate(data); elapsed = time.perf_counter() - started
        self.assertEqual(len(result["layers"][0]["thicknessValues"]), 100)
        self.assertLess(elapsed, 5.0)

    def test_nonpositive_range_is_rejected(self):
        data = unsigned_request(); data["layers"][0]["withinLayerCovariance"]["ranges"][0] = 0
        with self.assertRaisesRegex(ValueError, "ranges"):
            self.generate(data)

    def test_effective_clip_tolerance_is_minimum_of_declared_and_machine(self):
        data = unsigned_request(); data["psdAudit"]["absoluteEigenTolerance"] = 0.0
        data["psdAudit"]["relativeEigenTolerance"] = 0.0
        audit = self.generate(data)["layers"][0]["psdAudit"]
        self.assertEqual(audit["effectiveClipToleranceX"], 0.0)
        self.assertEqual(audit["effectiveClipToleranceY"], 0.0)
        self.assertEqual(audit["negativeEigenPolicy"], "MinDeclaredAuditAndMachineRoundoff")


if __name__ == "__main__": unittest.main()
