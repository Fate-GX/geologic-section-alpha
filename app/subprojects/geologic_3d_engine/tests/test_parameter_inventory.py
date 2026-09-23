import json,unittest
from pathlib import Path
from geologic_3d_engine.profiles.parameter_evidence import validate_parameter_evidence
ROOT=Path(__file__).resolve().parents[1]
class ParameterInventoryTests(unittest.TestCase):
 @classmethod
 def setUpClass(c):c.data=json.loads((ROOT/"examples"/"stage2_11_parameter_requirements_v1.json").read_text(encoding="utf-8"));c.req=c.data["requirements"]
 def test_inventory_has_28_unique_groups(s):s.assertEqual(len(s.req),28);s.assertEqual(len({x["parameterId"] for x in s.req}),28)
 def test_inventory_separates_parameter_classes(s):s.assertEqual({x["parameterClass"] for x in s.req},{"Geological","ProjectNumerical","GeologicalUncertainty","ObservationGeometry"})
 def test_every_requirement_has_units_dimensions_and_paths(s):s.assertTrue(all(x["unit"] and x["dimension"] and x["implementationPath"] for x in s.req))
 def test_synthetic_fixture_bindings_cover_inventory(s):
  bindings=[]
  for r in s.req:
   b={k:r[k] for k in ("parameterId","implementationPath","unit","dimension","valueKind")};b.update({"profileId":s.data["profileId"],"basisType":"SyntheticAssumption","scope":"DatasetSpecific","sourceIds":s.data["sourceIds"],"uncertainty":{"semantics":"Synthetic fixture value; no empirical uncertainty claim"},"applicability":{"statement":"Canonical Stage2-11 synthetic regression only"},"exclusions":["Not evidence for any real region"]})
   for key in ("value","range","fieldReference"):
    if key in r:b[key]=r[key]
   bindings.append(b)
  result=validate_parameter_evidence(s.req,bindings,set(s.data["sourceIds"]),s.data["profileId"]);s.assertTrue(result["passed"],result["errors"]);s.assertEqual(result["boundParameterCount"],28)
 def test_unexpected_duplicate_reports_record_count(s):
  rogue={"parameterId":"ROGUE"};result=validate_parameter_evidence([], [rogue,rogue],set(),s.data["profileId"]);error=next(x for x in result["errors"] if x["code"]=="UnexpectedParameterEvidence");s.assertEqual(error["recordCount"],2)
if __name__=="__main__":unittest.main()
