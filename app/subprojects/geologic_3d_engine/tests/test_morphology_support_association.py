import unittest
from geologic_3d_engine.section.morphology_support_association import associate_morphology_with_surface_support

def morphology(start=10,end=30,length=40):
 return {"schemaVersion":"ClosedMorphologyRouteIntervals-1.0","routeLengthM":length,
  "intervals":[{"intervalId":"R","startStationM":start,"endStationM":end}]}
def supports(classes=("PumiceCone","SurficialFallDepositDrape"),length=40):
 rows=[];bounds=[0,20,40]
 for i,c in enumerate(classes):rows.append({"supportId":f"S{i}","unitId":f"U{i}","symbol":str(i),
  "startStationM":bounds[i],"endStationM":bounds[i+1],"morphologyClass":c})
 return {"schemaVersion":"MappedSurfaceRouteSupport-1.0","routeLengthM":length,"intervals":rows}

class MorphologySupportAssociationTests(unittest.TestCase):
 def test_multiclass_overlap_cannot_use_scoria_equation(self):
  r=associate_morphology_with_surface_support(morphology(),supports());a=r["associations"][0]
  self.assertEqual(a["overlapCount"],2);self.assertFalse(a["scoriaConeMorphometryEligible"])
  self.assertEqual(a["classificationState"],"MultipleMappedMorphologyClasses_NoUniqueAssociation")
 def test_single_scoria_class_is_only_eligible_not_identified(self):
  r=associate_morphology_with_surface_support(morphology(5,15),supports(("ScoriaConeAndLavaFlowApron","PumiceCone")))
  a=r["associations"][0];self.assertTrue(a["scoriaConeMorphometryEligible"])
  self.assertFalse(a["namedVolcanoIdentityAuthorized"]);self.assertFalse(r["subsurfaceGeometryAuthorized"])
 def test_gap_and_route_mismatch_rejected(self):
  bad=supports();bad["intervals"][0]["endStationM"]=15
  with self.assertRaises(ValueError):associate_morphology_with_surface_support(morphology(),bad)
  with self.assertRaises(ValueError):associate_morphology_with_surface_support(morphology(),supports(length=42))
 def test_wrong_domains_rejected(self):
  with self.assertRaises(ValueError):associate_morphology_with_surface_support({},supports())
