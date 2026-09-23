import json,tempfile,unittest
from pathlib import Path
from geologic_3d_engine.gui_gsj_transition import execute_gsj_transition_review
from geologic_3d_engine.section.gsj_transition_review import build_transition_review_template

class GuiGsjTransitionTests(unittest.TestCase):
    def test_review_to_persisted_contact_event(self):
        plan={"terrainProfile":[{"stationM":0,"elevationM":100},{"stationM":100,"elevationM":110}],
          "surfaceGeology":{"transitions":[{"leftSymbol":"A","rightSymbol":"B","lowerStationM":40,"upperStationM":60,
          "estimatedStationM":50,"uncertaintyM":10,"locatorStatus":"IntervalCensoredBetweenPointQueries"}]}}
        review=build_transition_review_template(plan);review.update(reviewer="R",reviewedAt="T",reviewStatus="GeologistInterpreted")
        review["assignments"]=[{"transitionId":"GSJ-TRANSITION-0","contactIndex":1,"selectedStationM":50,"unitPair":["A","B"]}]
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/"plan.json";r=root/"review.json";p.write_text(json.dumps(plan),encoding="utf-8");r.write_text(json.dumps(review),encoding="utf-8")
            result,target=execute_gsj_transition_review(p,r,root)
            self.assertTrue(target.is_file());self.assertEqual(result["events"][0]["horizontalUncertaintyM"],10)
if __name__=="__main__":unittest.main()
