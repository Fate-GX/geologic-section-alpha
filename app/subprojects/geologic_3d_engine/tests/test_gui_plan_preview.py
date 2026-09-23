import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import Image

from geologic_3d_engine.gui_plan_preview import (attach_mapped_point_evidence,
    attach_mapped_linework_evidence, execute_plan_preview)
from geologic_3d_engine.gui_conditions import GeographicRouteConditions


def signed(payload):
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()
    return {**payload, "recordSha256": digest}


class GuiPlanMappedPointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.image = root / "preview.png"
        Image.new("RGB", (800, 600), "white").save(self.image)
        self.plan = root / "plan.json"
        self.plan.write_text(json.dumps({"routeLonLat":[[131.0,32.8],[131.01,32.81]]}),
                             encoding="utf-8")
        self.points = root / "points.json"
        base = {"schemaVersion":"GsjMappedPointEvidence-1.0", "featureCount":1,
                "features":[{"featureId":"P1","longitude":131.005,"latitude":32.806,
                  "featureKind":"HotSpring","sourceLabel":"温泉","sourceId":"OFFICIAL-1",
                  "sourceUrl":"https://example.invalid/source","horizontalCrs":"EPSG:6668"}]}
        self.points.write_text(json.dumps(signed(base), ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_attaches_display_only_evidence(self):
        result = attach_mapped_point_evidence(self.image, self.plan, self.points, 1000)
        self.assertEqual(result["displayedFeatureCount"], 1)
        self.assertEqual(result["authorizationBoundary"],
                         "DisplayOnly_NoSubsurfaceSectionConstraint")
        self.assertFalse(result["features"][0]["sectionConstraintAuthorized"])

    def test_outside_buffer_is_retained_but_not_drawn(self):
        result = attach_mapped_point_evidence(self.image, self.plan, self.points, 0)
        self.assertEqual(result["displayedFeatureCount"], 0)
        self.assertEqual(result["features"][0]["displayState"], "OutsideDisplayBuffer")

    def test_tampering_is_rejected(self):
        value = json.loads(self.points.read_text(encoding="utf-8"))
        value["features"][0]["latitude"] += 0.01
        self.points.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            attach_mapped_point_evidence(self.image, self.plan, self.points, 1000)

    def test_hash_bound_linework_is_drawn_and_intersected(self):
        feature={"featureId":"C","kind":"Contact","verticesLonLat":[[131.005,32.79],[131.005,32.82]],
          "sourceId":"MAP","sourceUrl":"https://example.invalid/map","locationMethod":"MappedLine",
          "locationalConfidence":"ScaleLimited"}
        base={"schemaVersion":"GeographicLineworkEvidence-1.0","featureCount":1,"features":[feature]}
        linework=self.points.parent/"linework.json";linework.write_text(json.dumps(signed(base)),encoding="utf-8")
        plan={"routeLonLat":[[131.0,32.8],[131.01,32.8]],"terrainProfile":[
          {"stationM":0,"elevationM":100},{"stationM":1000,"elevationM":110}]}
        self.plan.write_text(json.dumps(plan),encoding="utf-8")
        result=attach_mapped_linework_evidence(self.image,self.plan,linework)
        self.assertEqual(len(result["routeIntersections"]["events"]),1)
        self.assertEqual(result["authorizationBoundary"],
          "MappedSurfaceIntersectionsOnly_NoSubsurfaceContinuation")
        # The lower terrain-profile panel must never receive plan linework.
        pixels=Image.open(self.image)
        self.assertEqual(pixels.getpixel((10,pixels.height-10)),(255,255,255))

    def test_preview_passes_selected_terrain_sampling_method(self):
        root=Path(self.temp.name); output=root/"out"/"current_plan_preview"
        output.mkdir(parents=True)
        Image.new("RGB",(10,10),"white").save(
            output/"current_aerial_and_arbitrary_terrain_profile.png")
        (output/"plan_evidence_bundle.json").write_text(json.dumps({
            "routeLonLat":[[131,32],[132,33]],"terrainProfile":[],
            "surfaceGeology":{"transitionBrackets":[]}}),encoding="utf-8")
        route=GeographicRouteConditions(((131,32),(132,33)),25,"NearestPixel")
        with patch("geologic_3d_engine.gui_plan_preview.subprocess.run") as run:
            run.return_value.returncode=0
            execute_plan_preview(root,root/"out",route)
        command=run.call_args.args[0]
        self.assertEqual(command[command.index("--terrain-sampling")+1],"NearestPixel")


if __name__ == "__main__":
    unittest.main()
