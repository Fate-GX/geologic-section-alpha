import hashlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

from geologic_3d_engine.gui_kunijiban_ranking import (
    candidate_table_rows,execute_kunijiban_candidate_ranking)
from tests.test_bed0300_xml import xml
from tests.test_bed0400_xml import xml as xml4


class Response(io.BytesIO):
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


class GuiKuniJibanRankingTests(unittest.TestCase):
    def test_mixed_versions_are_compared_without_authorization(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);index={"schemaVersion":"KuniJibanRouteCandidateIndex-1.0",
              "candidates":[{"providerRecordId":1,"projectionDistanceM":1000.0},
                            {"providerRecordId":2,"projectionDistanceM":2500.0}]}
            index["recordSha256"]=hashlib.sha256(json.dumps(index,sort_keys=True,
                separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
            source=root/"index.json";source.write_text(json.dumps(index),encoding="utf-8")
            responses=[Response(xml().encode("cp932")),Response(xml4(total="3.0").encode("cp932"))]
            with patch("geologic_3d_engine.gui_kunijiban_ranking.urllib.request.urlopen",
                       side_effect=responses):
                result,target=execute_kunijiban_candidate_ranking(source,root/"out",workers=1)
            rows=candidate_table_rows(result)
            self.assertTrue(target.is_file());self.assertEqual(len(rows),2)
            self.assertEqual({r["dtdVersion"] for r in rows},{"3.00","4.00"})
            self.assertTrue(all(not r["sectionConstraintAuthorized"] for r in rows))
            result["candidates"][0]["projectionDistanceM"]+=1
            with self.assertRaises(ValueError):candidate_table_rows(result)

    def test_invalid_worker_count_rejects_before_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/"index.json"
            source.write_text(json.dumps({"candidates":[{"providerRecordId":1}]}))
            with patch("geologic_3d_engine.gui_kunijiban_ranking.urllib.request.urlopen") as network:
                with self.assertRaises(ValueError):
                    execute_kunijiban_candidate_ranking(source,root,workers=5)
                network.assert_not_called()


if __name__=="__main__":unittest.main()
