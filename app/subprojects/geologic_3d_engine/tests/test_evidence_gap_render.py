from pathlib import Path
import tempfile
import unittest
from PIL import Image

from geologic_3d_engine.section.evidence_gap_render import render_evidence_gap_section


class EvidenceGapRenderTests(unittest.TestCase):
    def fixtures(self):
        plan={"schemaVersion":"PlanEvidenceBundle-1.0","terrainProfile":[
            {"stationM":0,"elevationM":100},{"stationM":50,"elevationM":110},
            {"stationM":100,"elevationM":105}]}
        readiness={"schemaVersion":"RouteEvidenceReadiness-1.0",
            "sectionGeometryAuthorized":False,
            "constraintStationDistribution":{"constraintStationCount":0},
            "currentRouteBoreholes":[{"boreholeId":"FAR","stationM":50,
                "projectionState":"Rejected","projectionDistanceM":900}]}
        crossings={"schemaVersion":"GsjRouteCrossingSideClassification-1.0",
            "crossings":[{"stationM":30,"terrainElevationM":106,
                "sideClassificationStatus":"MappedUnitTransition"},
                {"stationM":70,"sideClassificationStatus":"NonGeologicSurfaceBoundary"}]}
        return plan,readiness,crossings

    def test_unknown_section_is_rendered_without_lithology_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"gap.png"
            result=render_evidence_gap_section(*self.fixtures(),path,80,width=700,height=400)
            self.assertEqual(result["subsurfaceState"],"Unknown_NoAuthorizedGeometry")
            self.assertEqual(result["mappedSurfaceTransitionCount"],1)
            self.assertEqual(result["displayDepthMeaning"],
                             "ViewportOnly_NotEvidenceOfInvestigationDepth")
            with Image.open(path) as image:self.assertEqual(image.size,(700,400))

    def test_authorized_geometry_wrong_schema_and_bad_depth_are_rejected(self):
        plan,readiness,crossings=self.fixtures()
        readiness["sectionGeometryAuthorized"]=True
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                render_evidence_gap_section(plan,readiness,crossings,Path(folder)/"x.png")
        readiness["sectionGeometryAuthorized"]=False
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                render_evidence_gap_section(plan,readiness,crossings,Path(folder)/"x.png",0)


if __name__=="__main__":unittest.main()
