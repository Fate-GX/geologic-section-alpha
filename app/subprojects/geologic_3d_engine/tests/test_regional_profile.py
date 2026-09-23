import copy,unittest
from pathlib import Path
from geologic_3d_engine.config import load_config
from geologic_3d_engine.profiles.regional_profile import RegionalProfile,load_regional_profile
ROOT=Path(__file__).resolve().parents[1];E=ROOT/"examples"
class RegionalProfileTests(unittest.TestCase):
 @classmethod
 def setUpClass(c):c.config=load_config(E/"stage6_small_config.json");c.profile=load_regional_profile(E/"stage6_synthetic_regional_profile.json");c.data=c.profile.data
 def check(s,mutate,code):
  d=copy.deepcopy(s.data);mutate(d);r=RegionalProfile(d).validate_against(s.config);s.assertFalse(r["passed"]);s.assertIn(code,{x["code"] for x in r["errors"]})
 def test_canonical_profile_passes(s):s.assertTrue(s.profile.validate_against(s.config)["passed"])
 def test_country_alone_cannot_authorize(s):s.check(lambda d:d.update(geologicalContext={}),"MissingGeologicalContext")
 def test_profile_id_must_match_config(s):s.check(lambda d:d.update(profileId="OTHER"),"RegionalProfileIdMismatch")
 def test_crs_mismatch_rejected(s):s.check(lambda d:d["spatialApplicability"].update(horizontalCRS="OTHER"),"RegionalProfileCrsMismatch")
 def test_extent_outside_scope_rejected(s):s.check(lambda d:d["spatialApplicability"].update(bbox=[0,0,-10,10,10,10]),"ModelExtentOutsideRegionalProfile")
 def test_unknown_source_rejected(s):s.check(lambda d:d["sourceIds"].append("UNKNOWN"),"UnknownRegionalSource")
 def test_all_units_require_evidence(s):s.check(lambda d:d["unitEvidence"].pop(),"EvidenceCoverageMismatch")
 def test_all_events_require_evidence(s):s.check(lambda d:d["eventEvidence"].pop(),"EvidenceCoverageMismatch")
 def test_empty_environment_rejected(s):s.check(lambda d:d.update(environments=[]),"MissingEnvironment")
 def test_exclusions_are_mandatory(s):s.check(lambda d:d.update(exclusions=[]),"MissingExclusions")
if __name__=="__main__":unittest.main()
