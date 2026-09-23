import hashlib,json,tempfile,unittest
from pathlib import Path
from geologic_3d_engine.section.geographic_linework import load_geographic_linework_evidence

def signed(features):
    value={"schemaVersion":"GeographicLineworkEvidence-1.0",
           "featureCount":len(features),"features":features}
    value["recordSha256"]=hashlib.sha256(json.dumps(value,sort_keys=True,
      separators=(",",":"),ensure_ascii=False).encode()).hexdigest();return value

class GeographicLineworkEvidenceTests(unittest.TestCase):
    def write(self,value):
        root=tempfile.TemporaryDirectory();path=Path(root.name)/"x.json"
        path.write_text(json.dumps(value),encoding="utf-8");return root,path
    def test_valid_and_tampered(self):
        feature={"featureId":"C1","kind":"Contact"};root,path=self.write(signed([feature]))
        try:
            self.assertEqual(load_geographic_linework_evidence(path)["featureCount"],1)
            value=json.loads(path.read_text());value["features"][0]["kind"]="Fault"
            path.write_text(json.dumps(value));
            with self.assertRaisesRegex(ValueError,"hash mismatch"):load_geographic_linework_evidence(path)
        finally:root.cleanup()
    def test_duplicate_and_count_are_rejected(self):
        for value in (signed([{"featureId":"X"},{"featureId":"X"}]),signed([{"featureId":"X"}])):
            if len(value["features"])==1:
                value["featureCount"]=2;value["recordSha256"]=hashlib.sha256(json.dumps(
                  {k:v for k,v in value.items() if k!="recordSha256"},sort_keys=True,
                  separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
            root,path=self.write(value)
            try:
                with self.assertRaises(ValueError):load_geographic_linework_evidence(path)
            finally:root.cleanup()
if __name__=="__main__":unittest.main()
