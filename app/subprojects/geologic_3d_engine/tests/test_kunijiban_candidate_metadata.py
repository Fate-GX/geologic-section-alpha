import hashlib,json,unittest
from geologic_3d_engine.evidence.kunijiban_candidate_metadata import (build_ranked_candidate_metadata,
                                                                      extract_candidate_metadata)
from tests.test_bed0300_xml import xml


class KuniJibanCandidateMetadataTests(unittest.TestCase):
 def sign(self,value):
  value["recordSha256"]=hashlib.sha256(json.dumps(value,sort_keys=True,
   separators=(",",":"),ensure_ascii=False).encode()).hexdigest();return value

 def test_bed0300_codes_depth_and_hash_are_extracted(self):
  result=extract_candidate_metadata(xml().encode("cp932"))
  self.assertEqual(result["coordinateMethodClass"],"TopographicMapReading")
  self.assertEqual(result["declaredResolutionArcSeconds"],1.0)
  self.assertEqual(result["totalDepthM"],4.0);self.assertEqual(len(result["sourceXmlSha256"]),64)

 def test_ranking_is_bucketed_before_method_and_never_authorizes(self):
  index=self.sign({"schemaVersion":"KuniJibanRouteCandidateIndex-1.0","candidates":[
   {"providerRecordId":1,"projectionDistanceM":400.0},
   {"providerRecordId":2,"projectionDistanceM":1100.0}]})
  map_xml=xml().encode("cp932")
  survey_xml=xml().replace("<取得方法コード>02</取得方法コード>",
                           "<取得方法コード>01</取得方法コード>").encode("cp932")
  result=build_ranked_candidate_metadata(index,[(1,map_xml),(2,survey_xml)])
  self.assertEqual([x["providerRecordId"] for x in result["candidates"]],[1,2])
  self.assertTrue(all(not x["sectionConstraintAuthorized"] for x in result["candidates"]))

 def test_response_set_malformed_and_unsupported_version_reject(self):
  index=self.sign({"schemaVersion":"KuniJibanRouteCandidateIndex-1.0","candidates":[
   {"providerRecordId":1,"projectionDistanceM":1.0}]})
  for responses in ([],[(2,xml().encode("cp932"))]):
   with self.subTest(responses=responses),self.assertRaises(ValueError):
    build_ranked_candidate_metadata(index,responses)
  for raw in (b"<bad>",xml(version="9.99").encode("cp932")):
   with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,"no candidate metadata"):
    build_ranked_candidate_metadata(index,[(1,raw)])

 def test_one_unsupported_candidate_is_retained_after_supported_rows(self):
  index=self.sign({"schemaVersion":"KuniJibanRouteCandidateIndex-1.0","candidates":[
   {"providerRecordId":1,"projectionDistanceM":100.0},
   {"providerRecordId":2,"projectionDistanceM":100.0}]})
  result=build_ranked_candidate_metadata(index,[(1,xml().encode("cp932")),
    (2,xml(version="9.99").encode("cp932"))])
  self.assertEqual(result["parsedCandidateCount"],1);self.assertEqual(result["rejectedMetadataCount"],1)
  self.assertEqual(result["candidates"][-1]["xmlMetadata"]["detectedDtdVersion"],"9.99")

 def test_bed0400_uses_new_depth_tag_and_shared_coordinate_codes(self):
  from tests.test_bed0400_xml import xml as xml4
  result=extract_candidate_metadata(xml4(total="20.0").encode("cp932"))
  self.assertEqual(result["dtdVersion"],"4.00")
  self.assertEqual(result["totalDepthM"],20.0)
  self.assertEqual(result["coordinateMethodClass"],"SurveyIncludingGPS")
  self.assertEqual(result["declaredResolutionArcSeconds"],0.01)
  self.assertEqual(result["formatHorizontalCrs"],"EPSG:4612")


if __name__=="__main__":unittest.main()
