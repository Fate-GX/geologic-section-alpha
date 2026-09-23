import unittest
from geologic_3d_engine.section.geological_domain_classifier import classify_plan_geological_domain

def plan(labels,elevations=(100,180,240)):
 total=500.;stations=[0,250,500]
 return {"schemaVersion":"PlanEvidenceBundle-1.0",
  "terrainProfile":[{"stationM":s,"elevationM":z} for s,z in zip(stations,elevations)],
  "surfaceGeology":{"sourceId":"GSJ","sourceEdition":"V2","samples":[
   {"stationM":s,"legend":{"symbol":str(i),"lithology_ja":label,"lithology_en":"","title":label}}
   for i,(s,label) in enumerate(zip(stations,labels))]}}

class GeologicalDomainClassifierTests(unittest.TestCase):
 def test_volcanic_mountain_is_selected_from_geology_not_relief(self):
  result=classify_plan_geological_domain(plan(["安山岩 溶岩・火砕岩"]*3))
  self.assertEqual(result["geologicalDomain"],"VolcanicTerrain")
  self.assertEqual(result["landformContext"],"MountainousRelief")
  self.assertFalse(result["terrainDeterminedGeologicalDomain"])
 def test_flat_granite_remains_plutonic(self):
  result=classify_plan_geological_domain(plan(["花崗岩"]*3,(10,11,10)))
  self.assertEqual(result["geologicalDomain"],"PlutonicTerrain")
  self.assertEqual(result["landformContext"],"LowRelief")
 def test_route_length_weighting_can_override_sample_count(self):
  value=plan(["安山岩","安山岩","砂岩"])
  value["surfaceGeology"]["samples"]=[
   {"stationM":s,"legend":{"symbol":str(i),"lithology_ja":label,"lithology_en":"","title":label}}
   for i,(s,label) in enumerate([(0,"安山岩"),(400,"安山岩"),(490,"砂岩"),(495,"砂岩"),(500,"砂岩")])]
  result=classify_plan_geological_domain(value)
  self.assertEqual(result["geologicalDomain"],"VolcanicTerrain")
 def test_mixed_route_is_not_forced_to_one_domain(self):
  result=classify_plan_geological_domain(plan(["花崗岩","結晶片岩","砂岩"]))
  self.assertEqual(result["geologicalDomain"],"MixedGeologicalDomain")
 def test_unknown_labels_remain_unresolved(self):
  result=classify_plan_geological_domain(plan(["分類不能"]*3))
  self.assertFalse(result["passed"]);self.assertEqual(result["geologicalDomain"],"Unresolved")
 def test_gsj_marine_clastic_wording_is_sedimentary(self):
  result=classify_plan_geological_domain(plan(["海成層 砕屑岩"]*3,(40,60,45)))
  self.assertEqual(result["geologicalDomain"],"SedimentaryRockTerrain")

if __name__=="__main__":unittest.main()
