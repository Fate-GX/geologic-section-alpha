import copy,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from geologic_3d_engine.config import load_config
from geologic_3d_engine.events.event_spec import load_event_spec
from geologic_3d_engine.events.intrusion_spec import load_intrusion_spec
from geologic_3d_engine.geometry.mesh_spec import load_mesh_spec
from geologic_3d_engine.geometry.refinement_spec import load_refinement_spec
from geologic_3d_engine.physics.compaction_spec import load_compaction_spec
from geologic_3d_engine.physics.structural_spec import load_structural_spec
from geologic_3d_engine.section.section_spec import load_section_spec
from geologic_3d_engine.uncertainty.ensemble_spec import load_ensemble_spec
from geologic_3d_engine.fields.stochastic_thickness import generate_stochastic_thickness
from geologic_3d_engine.stochastic_pipeline import run_stochastic_to_section
import tests.test_stochastic_thickness as auth_tests
class PipelineTests(unittest.TestCase):
 @classmethod
 def setUpClass(c):
  e=ROOT/"examples";c.config=load_config(e/"stage6_small_config.json");c.specs=(load_event_spec(e/"stage3_event_spec.json"),load_compaction_spec(e/"stage6_compaction_spec.json"),load_structural_spec(e/"stage6_structural_spec.json"),load_intrusion_spec(e/"stage6_intrusion_spec.json"),load_mesh_spec(e/"stage7_mesh_spec.json"),load_refinement_spec(e/"stage8_refinement_spec.json"),load_ensemble_spec(e/"stage9_ensemble_spec.json"),load_section_spec(e/"stage10_section_spec.json"))
 def setUp(s):s.auth=auth_tests.StochasticThicknessTests();s.auth.setUp()
 def tearDown(s):s.auth.tearDown()
 def generated(s):
  d=auth_tests.unsigned_request();d["grid"]={"nx":5,"ny":5,"spacingX":20,"spacingY":20};a=d["layers"][0];a["unitId"]="OLD_UPPER";a["transform"]={"kind":"PowerPositivePart","mu":4.0,"beta":1.0};a["threshold"]=-3;b=copy.deepcopy(a);b["unitId"]="OLD_LOWER";b["transform"]["mu"]=6.0;d["layers"].append(b);q,c=s.auth.authorize(d);return generate_stochastic_thickness(q,authentication_context=c)
 def pipeline(s,r=None):return run_stochastic_to_section(s.config,r or s.generated(),[[40]*5 for _ in range(5)],["INTR","FILL"],*s.specs)
 def test_stage9_blocks_invalid_ensemble(s):
  r=s.pipeline();s.assertFalse(r["passed"]);s.assertEqual(r["stageTen"]["errors"][0]["code"],"BlockedByStageNine");s.assertTrue(r["stageTen"]["stageNine"]["stageEight"]["passed"])
 def test_source_hash(s):
  x=s.generated();s.assertEqual(s.pipeline(x)["sourcePayloadSha256"],x["payloadSha256"])
 def test_partition(s):s.assertTrue(s.pipeline()["adapterReport"]["voxelPartition"]["passed"])
 def test_determinism(s):
  x=s.generated();s.assertEqual(s.pipeline(x)["pipelinePayloadSha256"],s.pipeline(x)["pipelinePayloadSha256"])
 def test_tamper_rejects(s):
  x=s.generated();x["layers"][0]["thicknessValues"][0][0]+=1;s.assertFalse(s.pipeline(x)["passed"])
 def test_uncertainty_boundary(s):s.assertEqual(s.pipeline()["uncertaintyProjection"],"RepresentativeBaselineOnly")
 def test_failed_member_diagnostics_are_preserved(s):
  members=s.pipeline()["stageTen"]["stageNine"]["ensemble"]["members"];failed=[m for m in members if not m["passed"]];s.assertEqual(len(failed),3);codes={e["code"] for m in failed for d in m["failedGateDiagnostics"] for e in d["errors"]};s.assertIn("PreBrepTopologyRejected",codes);s.assertIn("VolumeConvergenceExceeded",codes)
 def test_preflight_rejection_has_typed_diagnostics(s):
  failed=[m for m in s.pipeline()["stageTen"]["stageNine"]["ensemble"]["members"] if not m["passed"]]
  rejected=[e for m in failed for d in m["failedGateDiagnostics"] for e in d["errors"] if e.get("code")=="PreBrepTopologyRejected"]
  s.assertEqual(len(rejected),2);s.assertTrue(all(e["touchEdgeCount"]>0 for e in rejected))
  s.assertTrue(all(any(c["classification"]=="IntraComponentTouchEdge" for u in e["unitAudits"] if u["unitId"]=="OLD_LOWER" for c in u["contacts"]) for e in rejected))
  s.assertTrue(all(not any(e.get("code")=="RefinedBrepFailed" for d in m["failedGateDiagnostics"] for e in d["errors"]) for m in failed))
if __name__=="__main__":unittest.main()
