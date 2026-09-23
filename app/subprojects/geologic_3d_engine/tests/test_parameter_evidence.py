import copy,unittest
from geologic_3d_engine.profiles.parameter_evidence import validate_parameter_evidence

REQ=[{"parameterId":"P-THICK","implementationPath":"stack.layers[0].thickness","unit":"m","dimension":"L","geometryAffecting":True},
     {"parameterId":"P-TITLE-FONT","implementationPath":"publication.titleFontSize","unit":"pt","dimension":"L","geometryAffecting":False}]
BIND={"parameterId":"P-THICK","implementationPath":"stack.layers[0].thickness","unit":"m","dimension":"L","profileId":"PROFILE-A","basisType":"SyntheticAssumption","valueKind":"Range","range":[5.0,10.0],"scope":"DatasetSpecific","sourceIds":["SRC"],"uncertainty":{"semantics":"Declared synthetic envelope"},"applicability":{"statement":"Canonical synthetic test only"},"exclusions":["Not transferable to a real region"]}
class ParameterEvidenceTests(unittest.TestCase):
 def check(s,mutate,code):
  b=copy.deepcopy(BIND);mutate(b);r=validate_parameter_evidence(REQ,[b],{"SRC"},"PROFILE-A");s.assertFalse(r["passed"]);s.assertIn(code,{e["code"] for e in r["errors"]})
 def test_canonical_binding_passes(s):s.assertTrue(validate_parameter_evidence(REQ,[BIND],{"SRC"},"PROFILE-A")["passed"])
 def test_missing_geometry_parameter_rejected(s):s.assertIn("ParameterEvidenceCoverageMismatch",{e["code"] for e in validate_parameter_evidence(REQ,[],{"SRC"},"PROFILE-A")["errors"]})
 def test_duplicate_binding_rejected(s):s.assertFalse(validate_parameter_evidence(REQ,[BIND,BIND],{"SRC"},"PROFILE-A")["passed"])
 def test_unit_mismatch_rejected(s):s.check(lambda b:b.update(unit="ft"),"ParameterUnitOrDimensionMismatch")
 def test_implementation_path_mismatch_rejected(s):s.check(lambda b:b.update(implementationPath="other"),"ParameterImplementationPathMismatch")
 def test_unknown_source_rejected(s):s.check(lambda b:b.update(sourceIds=["OTHER"]),"InvalidParameterSourceBinding")
 def test_profile_mismatch_rejected(s):s.check(lambda b:b.update(profileId="PROFILE-B"),"ParameterProfileMismatch")
 def test_invalid_range_rejected(s):s.check(lambda b:b.update(range=[10,5]),"InvalidParameterValueContract")
 def test_missing_uncertainty_rejected(s):s.check(lambda b:b.update(uncertainty={}),"MissingParameterUncertainty")
 def test_missing_exclusion_rejected(s):s.check(lambda b:b.update(exclusions=[]),"MissingParameterExclusions")
 def test_non_geometry_parameter_must_not_be_injected(s):
  b=copy.deepcopy(BIND);b["parameterId"]="P-TITLE-FONT";b["implementationPath"]="publication.titleFontSize";b["unit"]="pt";b["dimension"]="L";b["valueKind"]="Scalar";b["value"]=10
  s.assertIn("UnexpectedParameterEvidence",{e["code"] for e in validate_parameter_evidence(REQ,[BIND,b],{"SRC"},"PROFILE-A")["errors"]})
if __name__=="__main__":unittest.main()
