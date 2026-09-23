import copy,unittest
from geologic_3d_engine.section.section_faults import apply_vertical_throw

SECTION={"stationsM":[0,25,50,75,100],"contactElevationsM":[[0]*5,[10]*5,[20]*5],
 "activeMasks":[[True]*5,[True]*5],"realRegionAuthorized":True}
EVENT={"featureId":"F1","kind":"Fault","stationM":50,"sourceId":"MAP-F1"}
EVIDENCE={"faultId":"F1","verticalThrowM":4,"downthrownRouteSide":"AfterIntersection",
 "affectedContactIndices":[0,1,2],"sourceId":"MAP-F1","evidenceStatus":"Observed","uncertaintyM":1}

class SectionFaultTests(unittest.TestCase):
    def test_same_throw_applies_to_all_affected_contacts_on_one_side(self):
        original=copy.deepcopy(SECTION);result=apply_vertical_throw(SECTION,EVENT,EVIDENCE)
        self.assertEqual(SECTION,original)
        self.assertEqual(result["contactElevationsM"][0],[0,0,0,-4,-4])
        self.assertEqual(result["contactElevationsM"][2],[20,20,20,16,16])
        self.assertEqual(result["faultOperations"][0]["kinematicScope"],"VerticalThrowComparator_NotGeneralSlipOrBalancedRestoration")
        self.assertFalse(result["realRegionAuthorized"])
    def test_crossing_sample_is_not_arbitrarily_assigned(self):
        result=apply_vertical_throw(SECTION,EVENT,EVIDENCE)
        self.assertEqual(result["contactElevationsM"][0][2],0)
    def test_wrong_source_assumption_and_bad_indices_are_rejected(self):
        cases=[dict(EVIDENCE,sourceId="OTHER"),dict(EVIDENCE,evidenceStatus="SyntheticAssumption"),
               dict(EVIDENCE,affectedContactIndices=[0,0]),dict(EVIDENCE,verticalThrowM=-1)]
        for value in cases:
            with self.subTest(value=value),self.assertRaises(ValueError):apply_vertical_throw(SECTION,EVENT,value)
    def test_inconsistent_partial_displacement_is_rejected_if_order_reverses(self):
        bad=dict(EVIDENCE,verticalThrowM=20,affectedContactIndices=[2])
        with self.assertRaises(ValueError):apply_vertical_throw(SECTION,EVENT,bad)
if __name__=="__main__":unittest.main()
