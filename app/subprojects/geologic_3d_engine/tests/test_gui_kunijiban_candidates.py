import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from geologic_3d_engine.gui_kunijiban_candidates import execute_kunijiban_candidate_search

class Response(io.BytesIO):
 def __enter__(self):return self
 def __exit__(self,*args):self.close()

class GuiKuniJibanCandidateTests(unittest.TestCase):
 def test_official_candidates_remain_unverified_and_plan_bound(self):
  document={"header":{"success":True},"data":{"values":[{"id":5,"longitude":131.04,
    "latitude":32.88,"approval":"approved"}]}}
  raw=json.dumps(document).encode()
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);plan=root/"plan.json";plan.write_text(json.dumps({
    "schemaVersion":"PlanEvidenceBundle-1.0","routeLonLat":[[131.036,32.878],[131.04,32.88]]}),encoding="utf-8")
   with patch("geologic_3d_engine.gui_kunijiban_candidates.urllib.request.urlopen",
              side_effect=lambda *args,**kwargs:Response(raw)):
    result,target=execute_kunijiban_candidate_search(plan,root/"out")
   self.assertTrue(target.is_file());self.assertFalse(result["realSubsurfaceGeometryAuthorized"])
   self.assertEqual(result["candidates"][0]["evidenceStatus"],"UnverifiedProviderCandidate")
   self.assertEqual(len(result["planEvidenceSha256"]),64);self.assertEqual(len(result["recordSha256"]),64)
 def test_wrong_plan_schema_rejects_before_network(self):
  with tempfile.TemporaryDirectory() as folder:
   plan=Path(folder)/"plan.json";plan.write_text("{}")
   with self.assertRaises(ValueError):execute_kunijiban_candidate_search(plan,folder)

if __name__=="__main__":unittest.main()
