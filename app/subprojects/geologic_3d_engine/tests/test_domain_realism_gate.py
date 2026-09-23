import unittest
from geologic_3d_engine.validation.domain_realism_gate import audit_domain_model_realism

def model(domain="SedimentaryRockTerrain",architecture="DeformedSedimentaryStack"):
 x=[0,100,200,300,400];top=[100,101,100,99,100];layers=[]
 for i in range(6):
  bottom=[v-5-i for v in top];layers.append({"bottomElevationM":bottom});top=bottom
 return {"stationsM":x,"planGeologicalDomainClassification":{"geologicalDomain":domain},
  "composition":{"backgroundArchitecture":{"type":architecture,
   "weatheringRepresentation":"ParentRockState_NotSeparateThickBody"},"layersTopDown":layers},
  "syntheticEventArchitecture":{"eventLog":[{"eventType":"RegionalPriorNoLocalizedEvent"}]},
  "geologicalPriorDecision":{"localizedEventsAuthorized":False}}

class DomainRealismGateTests(unittest.TestCase):
 def test_compatible_model_passes_without_claiming_truth(self):
  result=audit_domain_model_realism(model())
  self.assertTrue(result["passed"]);self.assertFalse(result["localTruthEstablished"])
 def test_mismatch_and_unauthorized_local_event_fail(self):
  value=model(architecture="VolcanicPaleosurfaceStack")
  value["syntheticEventArchitecture"]["eventLog"]=[{"eventType":"Erosion"}]
  result=audit_domain_model_realism(value)
  self.assertFalse(result["passed"])
  self.assertIn("DomainArchitectureMismatch",result["errors"])
  self.assertIn("LocalizedEventWithoutRouteApplicableEvidence",result["errors"])
 def test_unexplained_near_vertical_contact_fails(self):
  value=model();value["composition"]["layersTopDown"][1]["bottomElevationM"][2]-=400
  self.assertIn("NearVerticalUnexplainedContact:1",audit_domain_model_realism(value)["errors"])

if __name__=="__main__":unittest.main()
