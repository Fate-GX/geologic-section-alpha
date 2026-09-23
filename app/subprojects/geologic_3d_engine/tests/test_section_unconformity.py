import copy,unittest
from geologic_3d_engine.section.section_unconformity import apply_erosion_fill

SECTION={"stationsM":[0,50,100],"terrainElevationM":[40,40,40],"contactElevationsM":[[0,0,0],[10,20,10],[30,30,30]],
 "activeMasks":[[True]*3,[True]*3],"units":[{"unitId":"A","normalizedLithology":"a"},{"unitId":"B","normalizedLithology":"b"}],
 "validation":{},"realRegionAuthorized":True}
def controls(values,key="SRC"):
    return [{"stationM":s,"valueM":v,"sourceId":key,"evidenceStatus":"Observed"} for s,v in zip((0,50,100),values)]
def evidence():return {"eventId":"E","positiveErosionIndicators":["positiveTruncation"],"erosionSurfaceControls":controls([25,15,25]),
 "youngerUnit":{"unitId":"Y","normalizedLithology":"gravel"},"fillThicknessControls":controls([5,5,5],"FILL")}

class UnconformityTests(unittest.TestCase):
    def test_erosion_then_fill_shares_effective_retained_top(self):
        original=copy.deepcopy(SECTION);result=apply_erosion_fill(SECTION,evidence())
        self.assertEqual(SECTION,original);event=result["stratigraphicEvents"][0]
        self.assertEqual(event["effectiveFillBaseM"],[25,15,25])
        self.assertEqual(result["contactElevationsM"][-1],[30,20,30])
        self.assertTrue(result["validation"]["erosionFillOrdered"]);self.assertFalse(result["realRegionAuthorized"])
    def test_surface_above_old_top_uses_old_top_not_artificial_gap(self):
        value=evidence();value["erosionSurfaceControls"]=controls([35,35,35])
        result=apply_erosion_fill(SECTION,value)
        self.assertEqual(result["stratigraphicEvents"][0]["effectiveFillBaseM"],[30,30,30])
        self.assertEqual(result["contactElevationsM"][-1],[35,35,35])
    def test_no_indicator_extrapolation_and_synthetic_controls_are_rejected(self):
        cases=[];x=evidence();x["positiveErosionIndicators"]=[];cases.append(x)
        x=evidence();x["erosionSurfaceControls"]=x["erosionSurfaceControls"][1:];cases.append(x)
        x=evidence();x["fillThicknessControls"][0]["evidenceStatus"]="SyntheticAssumption";cases.append(x)
        for value in cases:
            with self.subTest(value=value),self.assertRaises(ValueError):apply_erosion_fill(SECTION,value)
if __name__=="__main__":unittest.main()
