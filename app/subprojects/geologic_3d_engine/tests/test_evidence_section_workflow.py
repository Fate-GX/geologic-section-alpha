import unittest
from geologic_3d_engine.section.evidence_section_workflow import build_evidence_constrained_section


def plan(state="SubsurfaceInterpretationInputsPresent"):
    return {"schemaVersion":"PlanEvidenceBundle-1.0","authorizationState":state,
      "terrainProfile":[{"stationM":i*100,"longitude":131+i*.001,"latitude":32.8,
                         "elevationM":120+2*i} for i in range(5)]}

def points(value,key="elevationM",status="Observed"):
    coords=[(131,32.799),(131.004,32.799),(131.002,32.802),(131.001,32.801)]
    return [{"longitude":x,"latitude":y,key:value+i,"sourceId":f"S{i}",
             "evidenceStatus":status} for i,(x,y) in enumerate(coords)]


class EvidenceSectionWorkflowTests(unittest.TestCase):
    def test_ordered_positive_section(self):
        units=[{"unitId":"U1","normalizedLithology":"sandstone",
                "thicknessEvidence":points(8,"trueThicknessM")},
               {"unitId":"U2","normalizedLithology":"mudstone",
                "thicknessEvidence":points(12,"trueThicknessM")}]
        result=build_evidence_constrained_section(plan(),points(70),units)
        self.assertTrue(all(result["validation"].values()))
        self.assertGreater(result["minimumTrueThicknessM"],0)
        self.assertEqual(result["geometryPolicy"],
                         "SharedReferenceSurfacePlusPositiveLogThicknessFields")
        self.assertTrue(result["realRegionAuthorized"])
        self.assertFalse(result["subsurfaceCoverageComplete"])
        self.assertGreater(result["maximumUnconstrainedTopGapM"],0)

    def test_synthetic_input_never_authorizes_real_region(self):
        units=[{"unitId":"U","normalizedLithology":"volcanic rock",
                "thicknessEvidence":points(10,"trueThicknessM","SyntheticAssumption")}]
        result=build_evidence_constrained_section(plan(),points(80),units)
        self.assertEqual(result["interpretationStatus"],"SyntheticHypothesis")
        self.assertFalse(result["realRegionAuthorized"])

    def test_plan_without_subsurface_authorization_stays_synthetic(self):
        units=[{"unitId":"U","normalizedLithology":"sand",
                "thicknessEvidence":points(5,"trueThicknessM")}]
        result=build_evidence_constrained_section(plan("TerrainPlanOnly_NoSubsurfaceLithologyAuthorization"),
                                                  points(80),units)
        self.assertFalse(result["realRegionAuthorized"])

    def test_invalid_thickness_nodata_and_duplicate_units_are_rejected(self):
        unit={"unitId":"U","normalizedLithology":"sand",
              "thicknessEvidence":points(5,"trueThicknessM")}
        bad=dict(unit); bad["thicknessEvidence"]=points(-5,"trueThicknessM")
        with self.assertRaises(ValueError): build_evidence_constrained_section(plan(),points(80),[bad])
        p=plan(); p["terrainProfile"][2]["elevationM"]=None
        with self.assertRaises(ValueError): build_evidence_constrained_section(p,points(80),[unit])
        with self.assertRaises(ValueError): build_evidence_constrained_section(plan(),points(80),[unit,unit])


if __name__=="__main__": unittest.main()
