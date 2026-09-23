import json,tempfile,unittest
from pathlib import Path
from geologic_3d_engine.gui_reviewed_section import execute_reviewed_section
from geologic_3d_engine.section.borehole_correlation import canonical_sha256

class ReviewedSectionFaultTests(unittest.TestCase):
    def test_fault_evidence_is_applied_only_with_matching_intersection(self):
        holes=[]
        for i,(lon,lat) in enumerate(((131,32.8),(131.01,32.8),(131,32.81))):
            holes.append({"boreholeId":f"B{i}","sourceId":"SRC","sourceLonLat":[lon,lat],"projectionState":"Projected",
              "stationM":i*100,"projectionDistanceM":0,"collarElevationM":100,
              "intervals":[{"intervalIndex":0,"sourceLabel":"sand","normalizedLithology":"sand","topElevationM":100,"bottomElevationM":90}]})
        intake={"schemaVersion":"BoreholeSectionIntake-1.0","boreholes":holes}
        members=[{"boreholeId":f"B{i}","intervalIndex":0} for i in range(3)]
        review={"schemaVersion":"BoreholeCorrelationReview-1.0","correlationId":"C","reviewer":"R","reviewedAt":"T",
          "intakeSha256":canonical_sha256(intake),"reviewStatus":"GeologistInterpreted",
          "unitsBottomUp":[{"unitId":"U","normalizedLithology":"sand","members":members}]}
        plan={"schemaVersion":"PlanEvidenceBundle-1.0","authorizationState":"TerrainPlanOnly_NoSubsurfaceLithologyAuthorization",
          "terrainProfile":[{"stationM":i*50,"longitude":131+i*.0025,"latitude":32.8,"elevationM":105} for i in range(5)]}
        line={"events":[{"featureId":"F","kind":"Fault","stationM":100,"sourceId":"MAP","terrainElevationM":105}],"ambiguities":[]}
        fault={"faultEvidence":[{"faultId":"F","verticalThrowM":3,"downthrownRouteSide":"AfterIntersection",
          "affectedContactIndices":[0,1],"sourceId":"MAP","evidenceStatus":"Observed","uncertaintyM":1}]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            paths=[]
            for name,value in (("plan",plan),("intake",intake),("review",review),("line",line),("fault",fault)):
                path=root/f"{name}.json";path.write_text(json.dumps(value),encoding="utf-8");paths.append(path)
            section,_,image=execute_reviewed_section(*paths[:3],root,None,paths[3],paths[4])
            self.assertEqual(section["faultOperations"][0]["verticalThrowM"],3)
            self.assertTrue(image.is_file());self.assertFalse(section["realRegionAuthorized"])
if __name__=="__main__":unittest.main()
