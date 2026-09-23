import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from geologic_3d_engine.section.route_binding import build_route_binding
from geologic_3d_engine.section.route_evidence_workspace_render import render_route_evidence_workspace


def signed(value):
    value=dict(value);raw=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    value["recordSha256"]=hashlib.sha256(raw).hexdigest();return value


class RouteEvidenceWorkspaceRenderTests(unittest.TestCase):
    def test_unknown_section_and_unverified_borehole_remain_diagnostic(self):
        route=[[0,0],[.01,0]]
        workspace=signed({"schemaVersion":"RouteEvidenceWorkspace-1.0",
          "routeBinding":build_route_binding(route),"terrainProfile":[
          {"stationM":0,"elevationM":100},{"stationM":1000,"elevationM":120}],
          "surfaceGeology":{"mappedUnitIntervals":[{"symbol":"A","startStationM":0,
          "endStationM":1000}],"transitions":[]},"mappedLineworkEvidence":None,
          "boreholes":[{"boreholeId":"B","stationM":500,"collarElevationM":110,
          "elevationConstraintAuthorized":False,"intervals":[{"topElevationM":110,
          "bottomElevationM":90,"normalizedLithology":"sand"}]}],
          "structuralObservations":[],"inputArtifactSha256":{},
          "authorizationState":"EvidenceOverlayOnly_NoAutomaticSubsurfaceGeometry",
          "unknownPolicy":"NoEvidenceRemainsUnknown_NoInterpolationAcrossEvidenceGaps"})
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"w.json";image=Path(folder)/"w.png"
            source.write_text(json.dumps(workspace),encoding="utf-8")
            result=render_route_evidence_workspace(source,image,width=800,height=500)
            self.assertTrue(image.is_file())
            with Image.open(image) as rendered:self.assertEqual(rendered.size,(800,500))
            self.assertEqual(result["subsurfaceFill"],"Unknown")
            self.assertFalse(result["renderedBoreholes"][0]["absoluteElevationAuthorized"])
            self.assertEqual(result["lateralInterpolation"],"None")
    def test_tampering_and_small_canvas_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"w.json"
            source.write_text(json.dumps({"schemaVersion":"RouteEvidenceWorkspace-1.0",
              "recordSha256":"0"*64}),encoding="utf-8")
            with self.assertRaises(ValueError):render_route_evidence_workspace(source,Path(folder)/"x.png")
            with self.assertRaises(ValueError):render_route_evidence_workspace(source,Path(folder)/"x.png",width=20)

    def test_indeterminate_contact_width_is_not_invented_by_renderer(self):
        workspace=signed({"schemaVersion":"RouteEvidenceWorkspace-1.0",
          "terrainProfile":[{"stationM":0,"elevationM":100},{"stationM":100,"elevationM":110}],
          "surfaceGeology":{"mappedUnitIntervals":[],"transitions":[]},"boreholes":[],
          "structuralObservations":[]})
        uncertainty={"schemaVersion":"MappedContactPositionUncertainty-1.0","routeLengthM":100,
          "boundaryCount":1,"boundaries":[{"transitionId":"T","centerStationM":40,
          "method":"MapScaleOnly","lowerStationM":None,"upperStationM":None,
          "evidenceEligibleNumericZone":False}]}
        with tempfile.TemporaryDirectory() as folder:
            w=Path(folder)/"w.json";u=Path(folder)/"u.json";image=Path(folder)/"x.png"
            w.write_text(json.dumps(workspace),encoding="utf-8");u.write_text(json.dumps(uncertainty),encoding="utf-8")
            result=render_route_evidence_workspace(w,image,width=800,height=500,contact_uncertainty_path=u)
            item=result["renderedContactPositionUncertainty"][0]
            self.assertEqual(item["renderRole"],"ExactComputedCrossing_NumericWidthIndeterminate")
            self.assertNotIn("halfWidthM",item)

    def test_uncertainty_for_another_route_is_rejected(self):
        workspace=signed({"schemaVersion":"RouteEvidenceWorkspace-1.0",
          "terrainProfile":[{"stationM":0,"elevationM":100},{"stationM":100,"elevationM":110}]})
        uncertainty={"schemaVersion":"MappedContactPositionUncertainty-1.0","routeLengthM":101,
          "boundaryCount":0,"boundaries":[]}
        with tempfile.TemporaryDirectory() as folder:
            w=Path(folder)/"w.json";u=Path(folder)/"u.json"
            w.write_text(json.dumps(workspace),encoding="utf-8");u.write_text(json.dumps(uncertainty),encoding="utf-8")
            with self.assertRaises(ValueError):
                render_route_evidence_workspace(w,Path(folder)/"x.png",contact_uncertainty_path=u)

    def test_surface_morphology_interval_follows_terrain_without_filling_subsurface(self):
        workspace=signed({"schemaVersion":"RouteEvidenceWorkspace-1.0",
          "terrainProfile":[{"stationM":0,"elevationM":100},{"stationM":100,"elevationM":110}],
          "surfaceGeology":{},"boreholes":[],"structuralObservations":[]})
        morphology={"schemaVersion":"ClosedMorphologyRouteIntervals-1.0","routeLengthM":100,
          "intervalCount":1,"intervals":[{"intervalId":"R","startStationM":20,"endStationM":80}]}
        with tempfile.TemporaryDirectory() as folder:
            w=Path(folder)/"w.json";m=Path(folder)/"m.json"
            w.write_text(json.dumps(workspace),encoding="utf-8");m.write_text(json.dumps(morphology),encoding="utf-8")
            r=render_route_evidence_workspace(w,Path(folder)/"x.png",width=800,height=500,morphology_intervals_path=m)
            self.assertEqual(r["renderedSurfaceMorphologyIntervals"][0]["renderRole"],
              "MappedSurfaceCraterInterval_NoSubsurfaceInference")
            self.assertEqual(r["subsurfaceFill"],"Unknown")


if __name__=="__main__":unittest.main()
