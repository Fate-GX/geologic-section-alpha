import unittest
import numpy as np

from geologic_3d_engine.section.borehole_constraints import validate_borehole_boundaries
from geologic_3d_engine.section.fault_displacement import VerticalThrowFault
from geologic_3d_engine.section.interlocking_sections import audit_section_intersection


class EvidenceAndFaultTests(unittest.TestCase):
    def test_borehole_round_trip_and_failure(self):
        evaluator=lambda sid,xy:10+xy[:,0]+({"S0":0,"S1":5}[sid])
        hole={"boreholeId":"BH-X","xy":[2,3],"collarElevation":30,
              "verticalDatum":"SyntheticDatum","sourceId":"OBS-X","boundaries":[
              {"surfaceId":"S0","depth":18,"evidenceKind":"ObservedBoundary"},
              {"surfaceId":"S1","depth":13,"evidenceKind":"ObservedBoundary"}]}
        self.assertTrue(validate_borehole_boundaries([hole],evaluator,0)["passed"])
        bad={**hole,"boundaries":[{"surfaceId":"S0","depth":17,"evidenceKind":"ObservedBoundary"}]}
        result=validate_borehole_boundaries([bad],evaluator,.5)
        self.assertFalse(result["passed"]);self.assertEqual(result["errors"][0]["code"],"BoreholeBoundaryResidualExceeded")

    def test_fault_side_throw_and_evidence(self):
        fault=VerticalThrowFault("F1",[0,0],[10,0],"Left",7,"MAP-F1")
        np.testing.assert_allclose(fault.displacement([[2,3],[2,-3],[2,0]]),[-7,0,0])
        np.testing.assert_allclose(fault.apply([20,20,20],[[2,3],[2,-3],[2,0]]),[13,20,20])
        self.assertEqual(fault.evidence()["sourceId"],"MAP-F1")

    def test_interlocking_sections_match_and_detect_section_dependent_error(self):
        shared=lambda sid,xy,section: np.full(len(xy),{"A":10,"B":20}[sid])
        self.assertTrue(audit_section_intersection(shared,["A","B"],[4,5],"X","Y",0)["passed"])
        broken=lambda sid,xy,section: np.full(len(xy),10+(1 if section=="Y" else 0))
        result=audit_section_intersection(broken,["A"],[4,5],"X","Y",.1)
        self.assertFalse(result["passed"]);self.assertEqual(result["errors"][0]["code"],"InterlockingSectionMismatch")

    def test_invalid_fault_rejects(self):
        with self.assertRaises(ValueError):VerticalThrowFault("F",[0,0],[0,0],"Left",1,"S")
        with self.assertRaises(ValueError):VerticalThrowFault("F",[0,0],[1,0],"Up",1,"S")

    def test_borehole_boolean_numbers_are_rejected(self):
        evaluator=lambda surface_id,xy:np.zeros(len(xy))
        valid={"boreholeId":"BH","xy":[0,0],"collarElevation":10.0,
               "verticalDatum":"SyntheticDatum","sourceId":"SRC","boundaries":[]}
        with self.assertRaises(ValueError):
            validate_borehole_boundaries([dict(valid,collarElevation=True)],evaluator,1.0)
        invalid=dict(valid,boundaries=[{"surfaceId":"S","depth":True,"evidenceKind":"Observed"}])
        with self.assertRaises(ValueError):
            validate_borehole_boundaries([invalid],evaluator,1.0)
        with self.assertRaises(ValueError):
            validate_borehole_boundaries([valid],evaluator,True)


if __name__=="__main__":unittest.main()
