import copy,pathlib,sys,unittest
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from geologic_3d_engine.geometry.regular_grid import RegularGrid3D
from geologic_3d_engine.models import Extent3D
from geologic_3d_engine.fields.stochastic_thickness import generate_stochastic_thickness
from geologic_3d_engine.export.contract_integrity import canonical_json_bytes,sha256_hex
from geologic_3d_engine.stratigraphy.stochastic_stack_adapter import build_stack_from_stochastic_thickness
import tests.test_stochastic_thickness as auth_tests

class StochasticStackAdapterTests(unittest.TestCase):
 def setUp(self):
  self.auth=auth_tests.StochasticThicknessTests();self.auth.setUp();self.grid=RegularGrid3D.from_extent(Extent3D((0,0,-50),(100,100,50),(50,50,10)))
 def tearDown(self):self.auth.tearDown()
 def generated(self):
  data=auth_tests.unsigned_request();data["grid"]={"nx":2,"ny":2,"spacingX":50,"spacingY":50};data["layers"][0]["transform"]={"kind":"PowerPositivePart","mu":5.0,"beta":1.5};second=copy.deepcopy(data["layers"][0]);second["unitId"]="U2";second["threshold"]=0.5;second["transform"]["mu"]=3.0;data["layers"].append(second);request,context=self.auth.authorize(data);return generate_stochastic_thickness(request,authentication_context=context)
 def build(self,result=None):return build_stack_from_stochastic_thickness(grid=self.grid,top_surface=[[40,40],[40,40]],stochastic_result=result or self.generated(),expected_unit_ids=["U1","U2"])
 def rehash(self,result):
  result["payloadSha256"]=sha256_hex(canonical_json_bytes({k:v for k,v in result.items() if k!="payloadSha256"}));return result
 def test_positive_real_generator_to_stack(self):
  stack,report=self.build();self.assertTrue(report["stackValidation"]["passed"]);self.assertTrue(report["voxelPartition"]["passed"])
 def test_shared_contacts_are_exact_objects(self):
  stack,_=self.build();self.assertIs(stack.layers[0].bottom,stack.layers[1].top)
 def test_nonnegative_thickness_and_active_mask(self):
  stack,_=self.build()
  for layer in stack.layers:
   for y,row in enumerate(layer.thickness):
    for x,value in enumerate(row):self.assertGreaterEqual(value,0);self.assertEqual(layer.active[y][x],value>stack.zero_thickness_tolerance)
 def test_geometric_volume_identity(self):
  stack,report=self.build();area=self.grid.cell_size[0]*self.grid.cell_size[1]
  for layer in stack.layers:self.assertAlmostEqual(report["voxelPartition"]["unitGeometricVolumes"][layer.unit_id],sum(map(sum,layer.thickness))*area)
 def test_grid_mismatch_rejected(self):
  result=self.generated();result["grid"]["spacingX"]=25;self.rehash(result)
  with self.assertRaisesRegex(ValueError,"grid does not match"):self.build(result)
 def test_unit_order_mismatch_rejected(self):
  with self.assertRaisesRegex(ValueError,"order"):build_stack_from_stochastic_thickness(grid=self.grid,top_surface=[[40,40],[40,40]],stochastic_result=self.generated(),expected_unit_ids=["U2","U1"])
 def test_tampered_payload_rejected(self):
  result=self.generated();result["layers"][0]["thicknessValues"][0][0]+=1
  with self.assertRaisesRegex(ValueError,"hash mismatch"):self.build(result)
 def test_nonexperimental_status_rejected(self):
  result=self.generated();result["status"]="Accepted";self.rehash(result)
  with self.assertRaisesRegex(ValueError,"status"):self.build(result)
 def test_zero_thickness_is_preserved_as_inactive_pinchout_state(self):
  result=self.generated();self.assertGreater(sum(layer["zeroThicknessCount"] for layer in result["layers"]),0);stack,_=self.build(result);self.assertTrue(any(not value for layer in stack.layers for row in layer.active for value in row))
if __name__=="__main__":unittest.main()
