import unittest
from geologic_3d_engine.section.crater_dimension_audit import audit_declared_crater_dimensions

def linework(closed=True):
 return {"evidenceRole":"VolcanicSurfaceMorphology","features":[{"featureId":"R","kind":"CraterRim","closedMappedLine":closed,
  # A 0.00635-degree square has a maximum diagonal close to the declared 1 km.
  "verticesLonLat":[[0,0],[.00635,0],[.00635,.00635],[0,.00635],[0,0]]}]}
def profile(diameter=1000,role="OuterClosedRim"):
 return {"featureName":"X","rims":[{"featureId":"R","rimRole":role,"declaredDiameterM":diameter}],"formationRelations":["ash fill"]}

class CraterDimensionAuditTests(unittest.TestCase):
 def test_matching_closed_rim_is_surface_constraint_only(self):
  r=audit_declared_crater_dimensions(linework(),profile());self.assertTrue(r["allDimensionallyConsistent"])
  self.assertFalse(r["rims"][0]["subsurfaceDepthAuthorized"]);self.assertFalse(r["subsurfaceGeometryAuthorized"])
 def test_large_mismatch_is_reported_not_tuned(self):
  r=audit_declared_crater_dimensions(linework(),profile(100));self.assertEqual(r["rims"][0]["dimensionConsistency"],"Inconsistent")
 def test_open_outer_rim_and_bad_reference_rejected(self):
  with self.assertRaises(ValueError):audit_declared_crater_dimensions(linework(False),profile())
  p=profile();p["rims"][0]["featureId"]="missing"
  with self.assertRaises(ValueError):audit_declared_crater_dimensions(linework(),p)
 def test_inner_remnant_may_be_open_but_never_supplies_depth(self):
  r=audit_declared_crater_dimensions(linework(False),profile(1000,"InnerRemnantRim"))
  self.assertFalse(r["subsurfaceGeometryAuthorized"])
