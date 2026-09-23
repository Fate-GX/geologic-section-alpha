import unittest
from geologic_3d_engine.evidence.kunijiban_candidate_index import build_candidate_index,route_marker_tiles

class KuniJibanCandidateIndexTests(unittest.TestCase):
 def test_tiles_and_candidate_are_fail_closed(self):
  route=[[131.036,32.878],[131.0733,32.889]]
  self.assertEqual(set(route_marker_tiles(route)),{(7077,3302,13),(7077,3303,13),(7078,3302,13),(7078,3303,13)})
  response={"header":{"success":True},"data":{"values":[{"id":7,"longitude":131.04,
    "latitude":32.88,"approval":"approved"}]}}
  result=build_candidate_index(route,[((7077,3302,13),response)])
  self.assertEqual(result["candidateCount"],1)
  self.assertEqual(result["candidates"][0]["evidenceStatus"],"UnverifiedProviderCandidate")
  self.assertFalse(result["realSubsurfaceGeometryAuthorized"])
 def test_wrong_zoom_and_failed_response_reject(self):
  with self.assertRaises(ValueError):route_marker_tiles([[0,0],[1,1]],12)
  with self.assertRaises(ValueError):build_candidate_index([[0,0],[1,0]],[((0,0,13),{"header":{"success":False}})])

if __name__=="__main__":unittest.main()
