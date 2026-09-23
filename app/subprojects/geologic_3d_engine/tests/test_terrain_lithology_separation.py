import copy,unittest
from geologic_3d_engine.modeling.terrain_surface_model import build_terrain_surface_model
from geologic_3d_engine.modeling.lithology_section_model import generate_basic_relative_depth_lithology
from geologic_3d_engine.modeling.terrain_lithology_composer import compose_terrain_and_lithology
from geologic_3d_engine.modeling.provider_contract import provider_manifest,invoke_lithology_provider
from geologic_3d_engine.modeling.basic_provider import BasicCorrelatedLithologyProvider

LAYERS=[{"unitId":"U1","normalizedLithology":"sand","meanThicknessM":12,"color":"#ccaa66"},
        {"unitId":"U2","normalizedLithology":"mud","meanThicknessM":18,"color":"#777777"}]
def terrain(values):return build_terrain_surface_model([{"stationM":i*10,"elevationM":z} for i,z in enumerate(values)],source_id="DEM",source_sha256="a"*64,sampling_method="test")

class SeparationTests(unittest.TestCase):
 def test_lithology_hash_is_independent_of_terrain(self):
  stations=[0,10,20,30];a=generate_basic_relative_depth_lithology(stations,LAYERS,seed=4)
  compose_terrain_and_lithology(terrain([100,110,105,100]),a)
  compose_terrain_and_lithology(terrain([500,450,470,480]),a)
  b=generate_basic_relative_depth_lithology(stations,LAYERS,seed=4)
  self.assertEqual(a["artifactSha256"],b["artifactSha256"]);self.assertFalse(a["terrainInputAccepted"])
 def test_composer_changes_absolute_contacts_not_generated_thickness(self):
  lith=generate_basic_relative_depth_lithology([0,10,20,30],LAYERS,seed=8)
  a=compose_terrain_and_lithology(terrain([100]*4),lith);b=compose_terrain_and_lithology(terrain([200]*4),lith)
  self.assertEqual(a["layersTopDown"][0]["thicknessM"],b["layersTopDown"][0]["thicknessM"])
  self.assertNotEqual(a["terrainElevationM"],b["terrainElevationM"])
  self.assertEqual(a["layersTopDown"][0]["bottomElevationM"],a["layersTopDown"][1]["topElevationM"])
 def test_tampered_artifact_and_invalid_thickness_rejected(self):
  lith=generate_basic_relative_depth_lithology([0,10],LAYERS,seed=1);bad=copy.deepcopy(lith);bad["seed"]=2
  with self.assertRaises(ValueError):compose_terrain_and_lithology(terrain([1,2]),bad)
 def test_provider_extension_contract_is_versioned(self):
  class Future:provider_id="ImplicitFieldRBF-2";contract_version="LithologySectionModel-1.0"
  self.assertTrue(provider_manifest(Future())["replaceableWithoutTerrainOrGuiChanges"])
  Future.contract_version="2.0"
  with self.assertRaises(ValueError):provider_manifest(Future())
 def test_station_varying_mean_needs_no_terrain(self):
  model=generate_basic_relative_depth_lithology([0,10,20],[{"unitId":"U","normalizedLithology":"sand",
    "meanThicknessProfileM":[2,4,3]}],seed=17,range_m=20,log_std=0)
  self.assertEqual(model["layersTopDown"][0]["thicknessM"],[2,4,3]);self.assertFalse(model["terrainInputAccepted"])
 def test_common_provider_boundary_rejects_terrain_and_unknown_options(self):
  provider=BasicCorrelatedLithologyProvider()
  request={"layers":LAYERS,"seed":2,"rangeM":20,"logStd":.1}
  self.assertEqual(invoke_lithology_provider(provider,[0,10,20],request)["providerId"],provider.provider_id)
  with self.assertRaises(ValueError):invoke_lithology_provider(provider,[0,10],{**request,"terrainElevationM":[1,2]})
  with self.assertRaises(ValueError):invoke_lithology_provider(provider,[0,10],{**request,"secretTuning":1})
