import unittest
from geologic_3d_engine.modeling.domain_model_library import select_domain_model

class DomainModelLibraryTests(unittest.TestCase):
 def test_supported_domains_have_six_nonduplicated_units(self):
  for domain in ("VolcanicTerrain","SedimentaryRockTerrain","AccretionaryComplex",
                 "PlutonicTerrain","MetamorphicBelt"):
   model=select_domain_model(domain);ids=[row[0] for row in model["facies"]]
   self.assertEqual(len(ids),6);self.assertEqual(len(set(ids)),6)
   self.assertEqual(model["basisType"],"SyntheticAssumption")
 def test_unknown_domain_fails_to_specific_default(self):
  model=select_domain_model("Unresolved")
  self.assertIsNone(model["facies"])
  self.assertEqual(model["selectionStatus"],"NoSpecificReusableModel")

if __name__=="__main__":unittest.main()
