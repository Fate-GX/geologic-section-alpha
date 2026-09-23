import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from geologic_3d_engine.gui_kunijiban_record import execute_kunijiban_record_capture
from tests.test_bed0300_xml import xml
from tests.test_bed0400_xml import xml as xml4


class Response(io.BytesIO):
    headers = {"Content-Type": "application/xml"}
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


def sign(document):
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode()
    document["recordSha256"] = hashlib.sha256(raw).hexdigest()


class GuiKuniJibanRecordTests(unittest.TestCase):
    def fixture(self, root):
        plan = root / "plan.json"
        plan.write_text(json.dumps({"schemaVersion": "PlanEvidenceBundle-1.0",
            "routeLonLat": [[131.0, 32.8], [131.1, 32.9]]}), encoding="utf-8")
        index = {"schemaVersion": "KuniJibanRouteCandidateIndex-1.0",
            "planEvidenceSha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
            "candidates": [{"providerRecordId": 531032,
                "providerApprovalLabel": "notapproved"}]}
        sign(index)
        index_path = root / "index.json"
        index_path.write_text(json.dumps(index), encoding="utf-8")
        return plan, index_path

    def test_capture_is_plan_bound_screened_and_unauthorized(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); plan, index = self.fixture(root)
            with patch("geologic_3d_engine.evidence.kunijiban_bed0300.urllib.request.urlopen",
                       return_value=Response(xml().encode("cp932"))):
                result, raw_path, candidate_path, collection_path = execute_kunijiban_record_capture(
                    plan, index, 531032, root / "out")
            self.assertTrue(raw_path.is_file() and candidate_path.is_file() and collection_path.is_file())
            collection=json.loads(collection_path.read_text(encoding="utf-8"))
            self.assertEqual(len(collection["boreholes"]),1)
            self.assertEqual(collection["boreholes"][0]["providerRecordId"],531032)
            self.assertFalse(result["sectionConstraintAuthorized"])
            self.assertFalse(result["routeScreening"]["sectionConstraintAuthorized"])
            self.assertEqual(result["routeConstraintDecision"],
                             "Rejected_TransformAndIndividualAccuracyUnverified")

    def test_tampering_wrong_plan_and_unknown_id_reject_before_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); plan, index_path = self.fixture(root)
            index = json.loads(index_path.read_text())
            index["candidates"][0]["providerApprovalLabel"] = "approved"
            index_path.write_text(json.dumps(index))
            with patch("geologic_3d_engine.evidence.kunijiban_bed0300.urllib.request.urlopen") as network:
                with self.assertRaises(ValueError):
                    execute_kunijiban_record_capture(plan, index_path, 531032, root)
                network.assert_not_called()
            plan, index_path = self.fixture(root)
            plan.write_text(json.dumps({"schemaVersion": "PlanEvidenceBundle-1.0",
                "routeLonLat": [[130, 32], [131, 33]]}))
            with self.assertRaises(ValueError):
                execute_kunijiban_record_capture(plan, index_path, 531032, root)
            plan, index_path = self.fixture(root)
            with self.assertRaises(ValueError):
                execute_kunijiban_record_capture(plan, index_path, 999, root)

    def test_bed0400_candidate_uses_version_specific_parser_and_crs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);plan,index=self.fixture(root)
            with patch("geologic_3d_engine.evidence.kunijiban_bed0300.urllib.request.urlopen",
                       return_value=Response(xml4(total="3.0").encode("cp932"))):
                result,raw_path,_,collection_path=execute_kunijiban_record_capture(
                    plan,index,531032,root/"out")
            self.assertEqual(result["schemaVersion"],"KuniJibanBED0400Candidate-1.0")
            self.assertEqual(result["horizontalCrs"],"EPSG:4612")
            self.assertEqual(result["declaredReadingResolutionArcSeconds"],0.01)
            self.assertIn("bed0400",raw_path.name)
            self.assertFalse(json.loads(collection_path.read_text(encoding="utf-8"))
                             ["sectionConstraintAuthorized"])


if __name__ == "__main__": unittest.main()
