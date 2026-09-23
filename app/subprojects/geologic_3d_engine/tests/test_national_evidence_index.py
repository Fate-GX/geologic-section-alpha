import unittest
from geologic_3d_engine.evidence.national_evidence_index import (build_national_evidence_index,
 query_national_evidence,borehole_to_national_evidence_record)
from geologic_3d_engine.profiles.neighbor_evidence_inference import infer_from_national_evidence_index

def record(source="S",lon=138.0,lat=36.0):
 return {"sourceId":source,"sourceType":"BoreholeLog","authority":"A","canonicalUrl":"https://example.test",
  "title":"T","publicationDate":"2025","observationDate":"2020","basisType":"Observed",
  "horizontalCrs":"EPSG:6668","horizontalCrsStatus":"Verified","verticalDatum":"TP",
  "verticalDatumStatus":"Verified","coordinateAccuracyM":5.0,"bboxLonLat":[lon,lat,lon,lat],
  "geologicalProvince":"P","basinOrTerrane":"B","ageApplicability":"Q",
  "environmentApplicability":"E","lithologies":["砂","泥"],"lithologyVocabularyVersion":"V",
  "artifactSha256":"a"*64,"locator":"L","confidenceDimensions":{},"exclusions":[]}

class NationalEvidenceIndexTests(unittest.TestCase):
 def test_build_query_and_infer(self):
  index=build_national_evidence_index([record("A",138,36),record("B",138.01,36)])
  target={"targetId":"T","longitude":138.005,"latitude":36,
          "geologicalProvince":"P","ageApplicability":"Q","environmentApplicability":"E"}
  query=query_national_evidence(index,target,maximum_distance_m=2000)
  self.assertEqual(len(query["matches"]),2)
  result=infer_from_national_evidence_index(index,target,maximum_distance_m=2000)
  self.assertTrue(result["passed"]);self.assertEqual(result["evidenceWeight"],.5)
  self.assertEqual(result["universalPriorWeight"],.5)
 def test_derived_inference_cannot_become_evidence(self):
  value=record();value["basisType"]="DerivedInference"
  with self.assertRaises(ValueError):build_national_evidence_index([value])
 def test_crs_and_datum_are_preserved_from_borehole(self):
  hole={"sourceId":"K","sourceUrl":"https://example.test/k","longitude":138,"latitude":36,
   "horizontalCrs":"EPSG:6668","horizontalCrsStatus":"Verified","verticalDatum":"TP",
   "verticalDatumStatus":"Declared","intervals":[{"normalizedLithology":"砂"}]}
  converted=borehole_to_national_evidence_record(hole,title="K",publication_date="2024",
                                                  artifact_sha256="b"*64,locator="record 1")
  self.assertEqual(converted["horizontalCrs"],"EPSG:6668")
  self.assertEqual(converted["verticalDatumStatus"],"Declared")
  self.assertEqual(converted["lithologies"],["砂"])
 def test_distance_and_applicability_filter(self):
  index=build_national_evidence_index([record("NEAR"),record("FAR",140,36)])
  target={"longitude":138,"latitude":36,"geologicalProvince":"P",
          "ageApplicability":"Q","environmentApplicability":"E"}
  self.assertEqual([x["sourceId"] for x in query_national_evidence(index,target,
                    maximum_distance_m=1000)["matches"]],["NEAR"])

if __name__=="__main__":unittest.main()
