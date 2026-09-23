import json,tempfile,unittest
from pathlib import Path
from geologic_3d_engine.gui_mapped_contact_review import create_mapped_contact_review_template
from geologic_3d_engine.section.mapped_contact_review import canonical_sha256

class GuiMappedContactReviewTests(unittest.TestCase):
    def test_template_is_written_from_hash_bound_adjacency(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);row={"featureId":"C","stationM":1,
              "sideClassificationStatus":"MappedUnitTransition",
              "unitPair":[{"sourcePolygonFeatureId":1},{"sourcePolygonFeatureId":2}]}
            adjacency={"schemaVersion":"GsjRouteCrossingSideClassification-1.0","crossingCount":1,
              "crossings":[row],"authorizationBoundary":"MappedSurfaceAdjacencyOnly_NoSubsurfaceContinuation"}
            adjacency["recordSha256"]=canonical_sha256(adjacency)
            ap=root/"a.json";ap.write_text(json.dumps(adjacency),encoding="utf-8")
            cp=root/"c.json";cp.write_text(json.dumps({"unitsBottomUp":[{"unitId":"A"},{"unitId":"B"}]}),encoding="utf-8")
            result,target=create_mapped_contact_review_template(ap,cp,root/"out")
            self.assertTrue(target.is_file());self.assertEqual(len(result["candidates"]),1)
            self.assertEqual(result["reviewStatus"],"Draft_NotReviewed")
if __name__=="__main__":unittest.main()
