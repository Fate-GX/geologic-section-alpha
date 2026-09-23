import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

ADVANCED = Path(__file__).resolve().parents[1]
if str(ADVANCED) not in sys.path:
    sys.path.insert(0, str(ADVANCED))
ENGINE = ADVANCED.parent
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

from advanced_preview_layout import finalize_advanced_preview_layout


class AdvancedPreviewLayoutTests(unittest.TestCase):
    def _model(self, count=18):
        bodies = [{"unitId": f"U{i}", "activeMask": [True]} for i in range(count)]
        return {
            "syntheticEventArchitecture": {"renderBodies": bodies},
            "composition": {"layersTopDown": [{"unitId": f"U{count-1}"}]},
            "renderingLithologies": [
                {"unitId": f"U{i}", "label": f"岩相 {i:02d}（推定）", "color": "#887766"}
                for i in range(count)
            ],
            "mappedSurfaceAtStations": [
                {"symbol": "Q", "lithologyJa": "砂・泥", "formationAgeJa": "第四紀",
                 "color": "#999999"}
            ],
            "renderAudit": {"verticalExaggeration": 1.25,
                            "sourceAttributionText": "出典：試験データ"},
        }

    def test_many_lithologies_expand_canvas_and_keep_all_text_inside(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "preview.png"
            Image.new("RGB", (1800, 1160), "white").save(path)
            audit = finalize_advanced_preview_layout(self._model(), path)
            self.assertTrue(audit["passed"])
            self.assertGreater(audit["canvasPx"][1], 1160)
            self.assertEqual(audit["visibleLithologyCount"], 18)
            self.assertTrue(all(item["boxPx"][3] <= audit["canvasPx"][1]
                                for item in audit["textBoxes"]))

    def test_inactive_non_basement_unit_is_not_in_legend(self):
        model = self._model(3)
        model["syntheticEventArchitecture"]["renderBodies"][0]["activeMask"] = [False]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "preview.png"
            Image.new("RGB", (1800, 1160), "white").save(path)
            audit = finalize_advanced_preview_layout(model, path)
            self.assertEqual(audit["visibleLithologyCount"], 2)


if __name__ == "__main__":
    unittest.main()
