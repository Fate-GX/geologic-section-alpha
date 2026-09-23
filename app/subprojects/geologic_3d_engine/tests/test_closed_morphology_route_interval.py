import unittest
from geologic_3d_engine.section.closed_morphology_route_interval import build_closed_morphology_route_intervals

def doc(events):return {"interpretationState":"SurfaceMorphologyEvidence_NoLithologyBoundaryPromotion","events":events}
def event(station,closed=True,feature="R"):
 return {"kind":"CraterRim","featureId":feature,"stationM":station,"closedMappedLine":closed,
         "terrainElevationM":100+station,"sourceId":"MAP"}

class ClosedMorphologyRouteIntervalTests(unittest.TestCase):
 def test_two_crossings_create_one_surface_only_interval(self):
  r=build_closed_morphology_route_intervals(doc([event(30),event(10)]));x=r["intervals"][0]
  self.assertEqual((x["startStationM"],x["endStationM"],x["lengthM"]),(10,30,20))
  self.assertFalse(x["lithologyInferenceAuthorized"]);self.assertFalse(x["subsurfaceGeometryAuthorized"])
 def test_open_or_odd_crater_crossings_rejected(self):
  for events in ([event(1,False),event(2,False)],[event(1)]):
   with self.subTest(events=events):
    with self.assertRaises(ValueError):build_closed_morphology_route_intervals(doc(events))
 def test_non_crater_lines_do_not_become_perimeter_intervals(self):
  x=event(1);x["kind"]="Dike"
  self.assertEqual(build_closed_morphology_route_intervals(doc([x]))["intervalCount"],0)
 def test_wrong_classification_domain_rejected(self):
  with self.assertRaises(ValueError):build_closed_morphology_route_intervals({"events":[]})
