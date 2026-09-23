import tempfile
import unittest
from pathlib import Path

from geologic_3d_engine.evidence.kunijiban_bed0300 import (angular_resolution_metres,
                                                           normalize_captured_record)
from tests.test_bed0300_xml import xml


class KuniJibanBed0300Tests(unittest.TestCase):
    def test_candidate_is_normalized_but_never_authorized(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "record.xml"
            path.write_bytes(xml().encode("cp932"))
            result = normalize_captured_record(
                path, record_id=531032, provider_approval_label="notapproved")
        self.assertEqual(result["providerRecordId"], 531032)
        self.assertEqual(result["providerApprovalLabel"], "notapproved")
        self.assertEqual(result["horizontalCrs"], "EPSG:4612")
        self.assertEqual(result["verticalDatum"], "TokyoPeil")
        self.assertEqual(result["horizontalCrsStatus"], "Declared")
        self.assertEqual(result["verticalDatumStatus"], "Declared")
        self.assertEqual(result["collarElevationAccuracyStatus"], "Unverified")
        self.assertEqual(result["horizontalPositionAccuracyStatus"], "DeclaredResolutionOnly")
        self.assertEqual(result["coordinateAcquisitionInterpretation"], "TopographicMapReading")
        self.assertEqual(result["declaredReadingResolutionArcSeconds"], 1.0)
        self.assertAlmostEqual(result["nominalReadingResolutionMetresLonLat"][0],25.99,places=1)
        self.assertAlmostEqual(result["nominalReadingResolutionMetresLonLat"][1],30.81,places=1)
        self.assertFalse(result["elevationConstraintAuthorized"])
        self.assertFalse(result["sectionConstraintAuthorized"])
        self.assertEqual({x["evidenceStatus"] for x in result["intervals"]}, {"Unverified"})

    def test_identifier_and_dtd_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "record.xml"
            path.write_bytes(xml().encode("cp932"))
            for identifier in (0, -1, True, "1.5", "01"):
                with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                    normalize_captured_record(path, record_id=identifier)
            path.write_bytes(xml(version="4.00").encode("cp932"))
            with self.assertRaises(ValueError):
                normalize_captured_record(path, record_id=1)

    def test_resolution_conversion_rejects_invalid_inputs(self):
        for latitude,seconds in ((91,1),(0,0),(float("nan"),1)):
            with self.subTest(latitude=latitude,seconds=seconds),self.assertRaises(ValueError):
                angular_resolution_metres(latitude,seconds)


if __name__ == "__main__":
    unittest.main()
