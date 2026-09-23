import tempfile
import unittest
import json
from pathlib import Path

from PIL import Image

from geologic_3d_engine.section.borehole_route_role import classify_borehole_route_roles
from geologic_3d_engine.section.regional_borehole_context_render import render_regional_borehole_context
from geologic_3d_engine.gui_regional_borehole_context import execute_regional_borehole_context


def borehole():
    return {"boreholeId":"CTX-1", "longitude":131.0, "latitude":32.9,
        "collarElevationM":500.0, "totalDepthM":10.0, "horizontalCrs":"EPSG:6668",
        "verticalDatum":"TokyoPeil", "sourceId":"SOURCE-1",
        "sourceUrl":"https://example.invalid/1", "exchangeFormatVersion":"TEST",
        "horizontalCrsStatus":"Verified", "verticalDatumStatus":"Declared",
        "collarElevationAccuracyStatus":"Unverified",
        "horizontalPositionAccuracyStatus":"DeclaredResolutionOnly",
        "intervals":[{"topDepthM":0.0,"bottomDepthM":4.0,"sourceLabel":"砂礫",
            "normalizedLithology":"砂礫","termStatus":"Current","evidenceStatus":"Unverified",
            "broadMaterialClass":"CoarseGrainedSoil"},
            {"topDepthM":4.0,"bottomDepthM":10.0,"sourceLabel":"岩",
            "normalizedLithology":"岩","termStatus":"Unverified","evidenceStatus":"Unverified",
            "broadMaterialClass":"VolcanicRock"}]}


class RegionalBoreholeContextRenderTests(unittest.TestCase):
    def test_context_log_is_drawn_without_section_contacts(self):
        route=[[131.0,32.92],[131.02,32.92]]
        roles=classify_borehole_route_roles([borehole()],route,100,3000)
        plan={"schemaVersion":"PlanEvidenceBundle-1.0","routeLonLat":route}
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/"context.png"
            result=render_regional_borehole_context(plan,roles,{"boreholes":[borehole()]},target,
                                                     width=1000,height=650)
            self.assertEqual(result["drawnSectionContactCount"],0)
            self.assertFalse(result["absoluteElevationUsedForSectionGeometry"])
            self.assertEqual(result["columnIntervalCount"],2)
            with Image.open(target) as image:self.assertEqual(image.size,(1000,650))
            self.assertTrue(target.with_suffix(".json").exists())

    def test_direct_or_mismatched_records_cannot_use_context_renderer(self):
        route=[[131.0,32.9],[131.02,32.9]]
        verified=borehole()
        verified.update({"verticalDatumStatus":"Verified",
                         "collarElevationAccuracyStatus":"Verified",
                         "horizontalPositionAccuracyStatus":"Verified"})
        for row in verified["intervals"]:row["evidenceStatus"]="Observed"
        direct=classify_borehole_route_roles([verified],route,100,3000)
        plan={"schemaVersion":"PlanEvidenceBundle-1.0","routeLonLat":route}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                render_regional_borehole_context(plan,direct,{"boreholes":[verified]},Path(folder)/"x.png")
            context=classify_borehole_route_roles([borehole()],[[131,32.92],[131.02,32.92]],100,3000)
            changed=borehole();changed["longitude"]+=.001
            with self.assertRaises(ValueError):
                render_regional_borehole_context(
                    {"schemaVersion":"PlanEvidenceBundle-1.0","routeLonLat":[[131,32.92],[131.02,32.92]]},
                    context,{"boreholes":[changed]},Path(folder)/"y.png")

    def test_gui_backend_integrates_existing_plan_image_and_hashes_inputs(self):
        route=[[131.0,32.92],[131.02,32.92]]
        plan={"schemaVersion":"PlanEvidenceBundle-1.0","routeLonLat":route}
        roles=classify_borehole_route_roles([borehole()],route,100,3000)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);plan_path=root/"plan_evidence_bundle.json"
            role_path=root/"roles.json";hole_path=root/"holes.json"
            plan_path.write_text(json.dumps(plan),encoding="utf-8")
            role_path.write_text(json.dumps(roles),encoding="utf-8")
            hole_path.write_text(json.dumps({"boreholes":[borehole()]}),encoding="utf-8")
            Image.new("RGB",(1000,600),"white").save(
                root/"current_aerial_and_arbitrary_terrain_profile.png")
            result,_,_,combined,evidence=execute_regional_borehole_context(
                plan_path,role_path,hole_path,root/"out")
            self.assertTrue(combined.is_file())
            document=json.loads(evidence.read_text(encoding="utf-8"))
            context=document["regionalBoreholeContext"]
            self.assertEqual(context["drawnSectionContactCount"],0)
            self.assertEqual(len(context["roleArtifactSha256"]),64)
            self.assertEqual(context["combinedImageState"],"Generated")


if __name__=="__main__":unittest.main()
