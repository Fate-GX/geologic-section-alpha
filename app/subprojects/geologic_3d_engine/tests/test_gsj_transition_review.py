import copy,unittest
from geologic_3d_engine.section.gsj_transition_review import build_transition_review_template,validate_transition_review

def plan():return {"terrainProfile":[{"stationM":0,"elevationM":100},{"stationM":100,"elevationM":110}],
 "surfaceGeology":{"transitions":[
  {"leftSymbol":"A","rightSymbol":None,"lowerStationM":10,"upperStationM":20,"estimatedStationM":15,"uncertaintyM":5,"locatorStatus":"IntervalCensoredBetweenPointQueries"},
  {"leftSymbol":"A","rightSymbol":"B","lowerStationM":40,"upperStationM":60,"estimatedStationM":50,"uncertaintyM":10,"locatorStatus":"IntervalCensoredBetweenPointQueries"}]}}

class GsjTransitionReviewTests(unittest.TestCase):
    def test_template_preserves_ineligible_nodata_and_review_bracket(self):
        data=plan();template=build_transition_review_template(data)
        self.assertEqual(template["candidates"][0]["reviewEligibility"],"Ineligible_NoMappedUnit")
        template.update(reviewer="R",reviewedAt="T",reviewStatus="GeologistInterpreted")
        template["assignments"]=[{"transitionId":"GSJ-TRANSITION-1","contactIndex":1,"selectedStationM":55,"unitPair":["A","B"]}]
        result=validate_transition_review(data,template);event=result["events"][0]
        self.assertEqual(event["terrainElevationM"],105.5);self.assertEqual(event["horizontalUncertaintyM"],15)
    def test_nodata_outside_bracket_pair_change_and_plan_tamper_are_rejected(self):
        data=plan();base=build_transition_review_template(data);base.update(reviewer="R",reviewedAt="T",reviewStatus="GeologistInterpreted")
        cases=[]
        for tid,station,pair in (("GSJ-TRANSITION-0",15,["A",None]),("GSJ-TRANSITION-1",70,["A","B"]),("GSJ-TRANSITION-1",50,["B","A"])):
            item=copy.deepcopy(base);item["assignments"]=[{"transitionId":tid,"contactIndex":0,"selectedStationM":station,"unitPair":pair}];cases.append((data,item))
        changed=copy.deepcopy(data);changed["terrainProfile"][0]["elevationM"]=99;item=copy.deepcopy(base);item["assignments"]=[];cases.append((changed,item))
        for p,r in cases:
            with self.subTest(review=r),self.assertRaises(ValueError):validate_transition_review(p,r)
if __name__=="__main__":unittest.main()
