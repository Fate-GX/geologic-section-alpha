import json
from pathlib import Path
import tempfile
import unittest

from advanced_v2.native_gate_artifact_audit import (
    NativeGateArtifactAuditError,
    audit_native_gate_artifacts,
)


class NativeGateArtifactAuditTests(unittest.TestCase):
    def _fixture(self, root: Path, identity="yuusuke"):
        target = root / "dwg"
        target.mkdir()
        name = "sample"
        dwg = target / f"{name}.dwg"
        report = target / f"{name}_reopen_validation.txt"
        record = target / f"{name}_run_record.json"
        dwg.write_bytes(b"AC1032fixture")
        report.write_text("ADVANCED_V2_REOPEN_VALIDATION=OK\n", encoding="utf-8")
        record.write_text(json.dumps({
            "decision": "NativeDwgGatePassed",
            "executionIdentity": identity,
            "profilePolicy": "CurrentDefault_NoArgImport_NoPersistentProfileChange",
            "dwg": str(dwg.resolve()),
            "reopenReport": str(report.resolve()),
        }), encoding="utf-8")
        return name, dwg, report, record

    def test_complete_evidence_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name, *_ = self._fixture(root)
            result = audit_native_gate_artifacts(root, name)
            self.assertTrue(result["passed"])
            self.assertEqual(set(result["artifacts"]), {"dwg", "reopenReport", "runRecord"})

    def test_missing_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name, _, report, _ = self._fixture(root)
            report.unlink()
            with self.assertRaisesRegex(NativeGateArtifactAuditError, "reopenReport"):
                audit_native_gate_artifacts(root, name)

    def test_sandbox_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name, *_ = self._fixture(root, "CodexSandboxOffline")
            with self.assertRaisesRegex(NativeGateArtifactAuditError, "execution identity"):
                audit_native_gate_artifacts(root, name)

    def test_run_record_path_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name, _, _, record = self._fixture(root)
            payload = json.loads(record.read_text(encoding="utf-8"))
            payload["dwg"] = str((root / "elsewhere.dwg").resolve())
            record.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(NativeGateArtifactAuditError, "promoted artifact"):
                audit_native_gate_artifacts(root, name)


if __name__ == "__main__":
    unittest.main()
