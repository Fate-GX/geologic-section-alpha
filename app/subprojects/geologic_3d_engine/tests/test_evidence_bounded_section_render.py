import tempfile
import unittest
from pathlib import Path

from PIL import Image

from geologic_3d_engine.section.evidence_bounded_section_render import render_evidence_bounded_section


class EvidenceBoundedSectionRenderTests(unittest.TestCase):
    def test_unknown_gap_creates_two_polygons_not_a_bridge(self):
        stations = [0, 10, 20, 30, 40]
        rows = []
        for station, supported in zip(stations, (True, True, False, True, True)):
            rows.append({"stationM": station,
                         "bottomElevationM": 70 if supported else None,
                         "topElevationM": 80 if supported else None,
                         "thicknessM": 10 if supported else None,
                         "coverageStatus": "BoundedByEvidence" if supported
                                           else "UnknownMissingBoundary"})
        section = {"schemaVersion": "EvidenceBoundedLithologySection-1.0",
                   "stationsM": stations, "terrainElevationM": [100] * 5,
                   "unitsBottomUp": [{"unitId": "U", "samples": rows}],
                   "realRegionAuthorization": "RequiresExternalReleaseGate"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "section.png"
            result = render_evidence_bounded_section(
                section, {"U": {"fillHex": "#aa8844", "displayLabel": "sandstone"}}, path)
            self.assertEqual(result["unitRenderAudit"][0]["polygonCount"], 2)
            self.assertFalse(result["unknownGapBridgingUsed"])
            with Image.open(path) as rendered:
                self.assertEqual(rendered.size, (1400, 700))

    def test_missing_style_and_bad_floor_reject(self):
        section = {"schemaVersion": "EvidenceBoundedLithologySection-1.0",
                   "stationsM": [0, 1], "terrainElevationM": [10, 10],
                   "unitsBottomUp": [{"unitId": "U", "samples": [
                       {"stationM": 0, "bottomElevationM": None, "topElevationM": None,
                        "coverageStatus": "UnknownMissingBoundary"},
                       {"stationM": 1, "bottomElevationM": None, "topElevationM": None,
                        "coverageStatus": "UnknownMissingBoundary"}]}],
                   "realRegionAuthorization": "RequiresExternalReleaseGate"}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                render_evidence_bounded_section(section, {}, Path(folder) / "x.png",
                                                display_floor_m=0)


if __name__ == "__main__":
    unittest.main()
