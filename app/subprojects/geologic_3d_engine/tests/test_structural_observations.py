import math
import unittest
from geologic_3d_engine.section.structural_observations import project_structural_observations,audit_section_apparent_dips

def observation(**changes):
    value={"observationId":"O1","longitude":131.005,"latitude":32.8001,
      "trueDipDegrees":30,"dipDirectionDegrees":90,"sourceId":"FIELD-1","sourceUrl":"https://example.invalid/field",
      "locationMethod":"GNSS","scientificConfidence":"Measured","locationalConfidence":"Surveyed"}
    value.update(changes);return value

class StructuralObservationTests(unittest.TestCase):
    def test_segment_specific_apparent_dip_on_bent_route(self):
        route=[(131,32.8),(131.01,32.8),(131.01,32.81)]
        east=project_structural_observations([observation()],route,100)[0]
        north=project_structural_observations([observation(observationId="O2",longitude=131.0101,latitude=32.805)],route,100)[0]
        self.assertAlmostEqual(east["sectionAzimuthDegrees"],90)
        self.assertAlmostEqual(east["apparentDipDegrees"],30)
        self.assertAlmostEqual(north["sectionAzimuthDegrees"],0)
        self.assertAlmostEqual(north["apparentDipDegrees"],0,places=10)
        self.assertEqual(east["sourceLonLat"],[131.005,32.8001])

    def test_apparent_dip_residual_audit_pass_and_fail(self):
        stations=[0,50,100,150];angle=20;slope=math.tan(math.radians(angle))
        section={"stationsM":stations,"contactElevationsM":[[10+s*slope for s in stations]]}
        base={"projectionState":"Projected","stationM":50,"apparentDipDegrees":angle,
              "observationId":"P","sourceId":"S"}
        result=audit_section_apparent_dips(section,[base],0,1)
        self.assertTrue(result["passed"]);self.assertAlmostEqual(result["residuals"][0]["signedResidualDegrees"],0)
        bad=dict(base,apparentDipDegrees=-20)
        self.assertFalse(audit_section_apparent_dips(section,[bad],0,5)["passed"])

    def test_rejected_observations_do_not_become_constraints(self):
        projected=project_structural_observations([observation(latitude=32.82)],[(131,32.8),(131.01,32.8)],10)
        self.assertEqual(projected[0]["projectionState"],"Rejected")
        section={"stationsM":[0,1,2],"contactElevationsM":[[0,0,0]]}
        audit=audit_section_apparent_dips(section,projected)
        self.assertEqual(audit["observationCount"],0);self.assertFalse(audit["passed"])

    def test_invalid_provenance_and_dip_are_rejected(self):
        for item in (observation(trueDipDegrees=91),observation(sourceId=""),observation(longitude=float("nan"))):
            with self.subTest(item=item),self.assertRaises(ValueError):
                project_structural_observations([item],[(131,32.8),(131.01,32.8)],100)
if __name__=="__main__":unittest.main()
