import json
import unittest
from pathlib import Path

from geologic_3d_engine.export.arbitrary_route_dwg import build_arbitrary_route_dwg_contract


ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "research/geologic_dwg_generation/outputs/chiba_sedimentary_500m_20260908/section/model.json"


class ArbitraryRouteDwgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = json.loads(MODEL.read_text(encoding="utf-8"))

    def test_contract_uses_exact_station_extent_and_drafting(self):
        result = build_arbitrary_route_dwg_contract(self.model)
        self.assertAlmostEqual(result["drafting"]["actualSectionLengthM"], self.model["stationsM"][-1])
        self.assertTrue(result["drafting"]["bilateralElevationTicks"])
        self.assertTrue(result["drafting"]["elevationTicksM"])
        self.assertEqual(result["terrainLine"]["vertices"][0], [0.0, self.model["terrainElevationM"][0]])

    def test_contacts_are_foremost_and_share_body_top(self):
        result = build_arbitrary_route_dwg_contract(self.model)
        self.assertTrue(result["contactLines"])
        self.assertTrue(all(v["drawOrder"] == "Foremost" for v in result["contactLines"]))
        first = result["polygons"][0]
        contact = result["contactLines"][0]
        self.assertEqual(first["vertices"][:len(contact["vertices"])], contact["vertices"])

    def test_rejects_unaudited_or_authorized_claim(self):
        bad = dict(self.model)
        bad["realRegionAuthorized"] = True
        with self.assertRaises(ValueError):
            build_arbitrary_route_dwg_contract(bad)

if __name__ == "__main__":
    unittest.main()
