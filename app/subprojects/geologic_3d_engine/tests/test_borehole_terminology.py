import copy
import json
import unittest
from pathlib import Path

from geologic_3d_engine.section.borehole_terminology import normalize_borehole_terminology


ROOT = Path(__file__).resolve().parents[3]
PROFILE = ROOT / "research" / "geologic_dwg_generation" / "datasets" / "bed_borehole_lithology_terminology_v1.json"


class BoreholeTerminologyTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.collection = {"boreholes": [{"boreholeId": "X", "intervals": [
            {"sourceLabel": "火山灰質粘性土", "evidenceStatus": "Unverified"},
            {"sourceLabel": "安山岩質玄武岩", "evidenceStatus": "Unverified"}]}],
            "sectionConstraintAuthorized": False}

    def test_exact_terms_preserve_source_and_do_not_authorize(self):
        result = normalize_borehole_terminology(self.collection, self.profile)
        terms = result["boreholes"][0]["intervals"]
        self.assertEqual(terms[0]["sourceLabel"], "火山灰質粘性土")
        self.assertEqual(terms[0]["fieldSymbol"], "V")
        self.assertEqual(terms[1]["broadMaterialClass"], "VolcanicRock")
        self.assertEqual(terms[1]["termStatus"], "Unverified")
        self.assertFalse(result["sectionConstraintAuthorized"])
        self.assertFalse(terms[0]["formalEngineeringClassificationAuthorized"])
        already = copy.deepcopy(self.collection)
        already["sectionConstraintAuthorized"] = True
        self.assertTrue(normalize_borehole_terminology(already, self.profile)["sectionConstraintAuthorized"])

    def test_unknown_label_is_retained_and_reported(self):
        source = copy.deepcopy(self.collection)
        source["boreholes"][0]["intervals"][0]["sourceLabel"] = "独自現場名"
        result = normalize_borehole_terminology(source, self.profile)
        item = result["boreholes"][0]["intervals"][0]
        self.assertEqual(item["normalizedLithology"], "独自現場名")
        self.assertEqual(item["termStatus"], "Unverified")
        self.assertEqual(result["terminologyNormalizationState"], "PartialUnresolved")

    def test_duplicate_and_authorization_escalation_reject(self):
        bad = copy.deepcopy(self.profile)
        bad["terms"].append(copy.deepcopy(bad["terms"][0]))
        with self.assertRaises(ValueError):
            normalize_borehole_terminology(self.collection, bad)
        bad = copy.deepcopy(self.profile)
        bad["terms"][0]["formalEngineeringClassificationAuthorized"] = True
        with self.assertRaises(ValueError):
            normalize_borehole_terminology(self.collection, bad)


if __name__ == "__main__":
    unittest.main()
