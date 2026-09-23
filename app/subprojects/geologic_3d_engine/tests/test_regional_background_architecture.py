import unittest
import numpy as np
from geologic_3d_engine.modeling.regional_background_architecture import (apply_volcanic_paleosurface_stack,
 apply_deformed_sedimentary_stack,apply_plutonic_weathering_mass)

class RegionalBackgroundArchitectureTests(unittest.TestCase):
 def source(self):
  x=np.linspace(0,500,51);terrain=200+8*np.sin(x/70)-.12*x;layers=[];top=terrain
  for i,mean in enumerate((2,7,15,22,28,75)):
   bottom=top-mean;layers.append({"unitId":"SYN-SURFACE-COVER" if i==0 else str(i),"topElevationM":top.tolist(),
    "bottomElevationM":bottom.tolist(),"thicknessM":[mean]*len(x)});top=bottom
  return {"schemaVersion":"X","stationsM":x.tolist(),"terrainElevationM":terrain.tolist(),
          "layersTopDown":layers,"artifactSha256":"ignored","compositionMethod":"old"}
 def test_contacts_are_shared_positive_and_not_terrain_offsets(self):
  x=np.linspace(0,500,51);terrain=200+8*np.sin(x/70)-.12*x
  layers=[];top=terrain
  for i,mean in enumerate((3,7,15,22,28,75)):
   bottom=top-mean;layers.append({"unitId":"SYN-SURFACE-COVER" if i==0 else str(i),"topElevationM":top.tolist(),
    "bottomElevationM":bottom.tolist(),"thicknessM":[mean]*len(x)});top=bottom
  source={"schemaVersion":"X","stationsM":x.tolist(),"terrainElevationM":terrain.tolist(),
          "layersTopDown":layers,"artifactSha256":"ignored","compositionMethod":"old"}
  result=apply_volcanic_paleosurface_stack(source,seed=22,dip_degrees=-7)
  for upper,lower in zip(result["layersTopDown"],result["layersTopDown"][1:]):
   self.assertEqual(upper["bottomElevationM"],lower["topElevationM"])
  self.assertTrue(all(min(v["thicknessM"])>=0 for v in result["layersTopDown"]))
  self.assertLessEqual(max(result["layersTopDown"][0]["thicknessM"]),5.0)
  deepest=np.asarray(result["layersTopDown"][-2]["bottomElevationM"])
  self.assertGreater(np.ptp(deepest-terrain),.15*np.ptp(terrain))
  self.assertEqual(result["backgroundArchitecture"]["modernTerrainRole"],
                   "UpperTruncationEnvelopeOnly")
 def test_sedimentary_and_plutonic_models_preserve_partition(self):
  for function in (apply_deformed_sedimentary_stack,apply_plutonic_weathering_mass):
   result=function(self.source(),seed=29)
   for upper,lower in zip(result["layersTopDown"],result["layersTopDown"][1:]):
    self.assertEqual(upper["bottomElevationM"],lower["topElevationM"])
   self.assertTrue(all(min(row["thicknessM"])>=0 for row in result["layersTopDown"]))
 def test_sedimentary_contacts_are_not_terrain_copies(self):
  source=self.source();result=apply_deformed_sedimentary_stack(source,seed=31)
  terrain=np.asarray(source["terrainElevationM"])
  residual=np.asarray(result["layersTopDown"][3]["bottomElevationM"])-terrain
  self.assertGreater(np.ptp(residual),10.0)
 def test_plutonic_model_declares_non_bedding_state_fronts(self):
  result=apply_plutonic_weathering_mass(self.source(),seed=37)
  self.assertEqual(result["backgroundArchitecture"]["weatheringRepresentation"],
                   "GradedParentRockState_NotStratigraphicBeds")

if __name__=="__main__":unittest.main()
