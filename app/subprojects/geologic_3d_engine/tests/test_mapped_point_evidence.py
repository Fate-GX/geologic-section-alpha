import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from geologic_3d_engine.section.mapped_point_evidence import (
    load_gsj_mapped_point_evidence, normalize_mapped_point,
    project_mapped_points_to_geographic_route)


def point(**changes):
    value = {"featureId":"P1", "longitude":131.0, "latitude":32.88,
             "featureKind":"HotSpring", "sourceLabel":"温泉", "sourceId":"GSJ-X",
             "sourceUrl":"https://example.invalid/map", "horizontalCrs":"EPSG:6668"}
    value.update(changes)
    return value


class MappedPointEvidenceTests(unittest.TestCase):
    def test_surface_feature_is_displayable_but_never_section_constraint(self):
        result = project_mapped_points_to_geographic_route(
            [point(latitude=32.8801)], [[131.0,32.88],[131.01,32.88]], 20.0)[0]
        self.assertEqual(result["displayState"], "WithinDisplayBuffer")
        self.assertEqual(result["interpretationBoundary"], "SurfaceHydrothermalFeatureOnly")
        self.assertFalse(result["sectionConstraintAuthorized"])

    def test_drill_symbol_without_log_remains_presence_only(self):
        result = normalize_mapped_point(point(featureKind="DrillHoleReachedBasement",
                                              sourceLabel="基盤に達した試錐",
                                              sourceAttributes={"Attribute2":242.0}))
        self.assertEqual(result["interpretationBoundary"],
                         "RegionalSubsurfacePresenceOnly_NoIntervals")
        self.assertEqual(result["observationType"], "BasementReached")
        self.assertEqual(result["reportedNumericAttribute2"], 242.0)
        self.assertEqual(result["reportedNumericMeaningStatus"],
                         "Unverified_GenericSourceAttribute")
        self.assertFalse(result["individualDepthConstraintAuthorized"])
        self.assertFalse(result["sectionConstraintAuthorized"])

    def test_invalid_unknown_and_missing_records_fail_closed(self):
        cases = [point(longitude=float("nan")), point(featureKind="OutcropContact"),
                 point(horizontalCrs=""), {"featureId":"P"}]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                normalize_mapped_point(case)

    def test_outside_buffer_and_bad_route_are_explicit(self):
        result = project_mapped_points_to_geographic_route(
            [point(latitude=32.9)], [[131.0,32.88],[131.01,32.88]], 100.0)[0]
        self.assertEqual(result["displayState"], "OutsideDisplayBuffer")
        with self.assertRaises(ValueError):
            project_mapped_points_to_geographic_route([point()], [[131.0,32.88]], 10)

    def test_hash_bound_collection_rejects_tamper_and_duplicate(self):
        for duplicate, tamper in ((False,False),(False,True),(True,False)):
            with self.subTest(duplicate=duplicate,tamper=tamper), tempfile.TemporaryDirectory() as folder:
                features=[point()]
                if duplicate:
                    features.append(point())
                payload={"schemaVersion":"GsjMappedPointEvidence-1.0",
                         "featureCount":len(features),"features":features}
                payload["recordSha256"]=hashlib.sha256(json.dumps(payload,sort_keys=True,
                    separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
                if tamper:
                    payload["features"][0]["sourceLabel"]="改変"
                path=Path(folder)/"points.json"
                path.write_text(json.dumps(payload),encoding="utf-8")
                if duplicate or tamper:
                    with self.assertRaises(ValueError): load_gsj_mapped_point_evidence(path)
                else:
                    self.assertEqual(load_gsj_mapped_point_evidence(path)["featureCount"],1)


if __name__ == "__main__":
    unittest.main()
