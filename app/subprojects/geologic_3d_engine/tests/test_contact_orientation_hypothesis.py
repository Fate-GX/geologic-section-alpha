import copy
import hashlib
import json
import math
import unittest

from geologic_3d_engine.section.contact_orientation_hypothesis import (
    audit_contact_hypothesis_topology,
    build_contact_orientation_hypothesis_template,
    evaluate_contact_orientation_hypotheses)


def signed(value):
    value=copy.deepcopy(value)
    value["recordSha256"]=hashlib.sha256(json.dumps(value,sort_keys=True,
        separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return value


def intersections():
    return signed({"schemaVersion":"GeographicLineworkIntersections-1.0",
        "events":[{"featureId":"C1","kind":"Contact","stationM":100.0,
            "terrainElevationM":500.0,"sourceId":"MAP"}]})


class ContactOrientationHypothesisTests(unittest.TestCase):
    def test_template_preserves_anchor_and_authorizes_nothing(self):
        result=build_contact_orientation_hypothesis_template(intersections())
        self.assertEqual(result["hypotheses"][0]["anchorElevationM"],500)
        self.assertFalse(result["hypotheses"][0]["subsurfaceContinuationAuthorized"])
        self.assertEqual(evaluate_contact_orientation_hypotheses(result,{0:90})["evaluatedCount"],0)

    def test_signed_slope_and_support_follow_explicit_equation(self):
        template=build_contact_orientation_hypothesis_template(intersections())
        row=template["hypotheses"][0]
        row.update({"orientationBasis":"SyntheticAssumption","trueDipDegrees":30.0,
            "dipDirectionDegrees":90.0,"angularUncertaintyDegrees":5.0,
            "lateralSupportM":50.0,"basisSourceIds":[],"interpretationNote":"test"})
        template["recordSha256"]=hashlib.sha256(json.dumps(
            {k:v for k,v in template.items() if k!="recordSha256"},sort_keys=True,
            separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        result=evaluate_contact_orientation_hypotheses(template,{0:90})
        item=result["hypotheses"][0]
        self.assertAlmostEqual(item["apparentDipDegrees"],30)
        self.assertAlmostEqual(item["elevationSlopePerStation"],-math.tan(math.radians(30)))
        self.assertAlmostEqual(item["candidateEndpointsStationElevation"][1][1],
                               500-50*math.tan(math.radians(30)))
        self.assertFalse(result["realRegionAuthorized"])
        self.assertLess(item["elevationSlopeRangePerStation"][0],
                        item["elevationSlopePerStation"])
        self.assertGreater(item["uncertaintyEnvelope"][0]["maximumElevationM"],
                           item["uncertaintyEnvelope"][0]["minimumElevationM"])

    def test_tampering_and_premature_authorization_reject(self):
        template=build_contact_orientation_hypothesis_template(intersections())
        template["hypotheses"][0]["anchorStationM"]=99
        with self.assertRaises(ValueError):evaluate_contact_orientation_hypotheses(template,{0:90})

    def test_topology_distinguishes_proven_overlap_and_nominal_violation(self):
        source=signed({"schemaVersion":"GeographicLineworkIntersections-1.0",
            "events":[{"featureId":"TOP","kind":"Contact","stationM":100.0,
                "terrainElevationM":500.0,"sourceId":"MAP"},
                {"featureId":"BOTTOM","kind":"Contact","stationM":100.0,
                "terrainElevationM":450.0,"sourceId":"MAP"}]})
        template=build_contact_orientation_hypothesis_template(source)
        for row in template["hypotheses"]:
            row.update({"orientationBasis":"SyntheticAssumption","trueDipDegrees":20,
                "dipDirectionDegrees":90,"angularUncertaintyDegrees":2,
                "lateralSupportM":50,"basisSourceIds":[],"interpretationNote":"test"})
        template["recordSha256"]=hashlib.sha256(json.dumps(
            {k:v for k,v in template.items() if k!="recordSha256"},sort_keys=True,
            separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        evaluation=evaluate_contact_orientation_hypotheses(template,{0:90,1:90})
        relation={"aboveHypothesisId":"CONTACT-ORIENTATION-0000",
                  "belowHypothesisId":"CONTACT-ORIENTATION-0001",
                  "minimumSeparationM":1}
        audit=audit_contact_hypothesis_topology(evaluation,[relation])
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["relations"][0]["status"],"OrderProvenWithinDeclaredEnvelope")
        # Narrow the nominal separation while retaining angle uncertainty.
        shifted=copy.deepcopy(evaluation)
        for endpoint in shifted["hypotheses"][1]["candidateEndpointsStationElevation"]:
            endpoint[1]+=49.5
        for point in shifted["hypotheses"][1]["uncertaintyEnvelope"]:
            point["minimumElevationM"]+=49.5;point["maximumElevationM"]+=49.5
        audit=audit_contact_hypothesis_topology(shifted,[{**relation,"minimumSeparationM":0}])
        self.assertEqual(audit["relations"][0]["status"],"UncertaintyEnvelopeOverlap")
        violated=copy.deepcopy(shifted)
        for endpoint in violated["hypotheses"][1]["candidateEndpointsStationElevation"]:
            endpoint[1]+=1
        audit=audit_contact_hypothesis_topology(violated,[{**relation,"minimumSeparationM":0}])
        self.assertEqual(audit["relations"][0]["status"],"NominalOrderViolation")
        template=build_contact_orientation_hypothesis_template(intersections())
        template["hypotheses"][0].update({"orientationBasis":"IndependentlyVerified",
            "trueDipDegrees":20,"dipDirectionDegrees":90,
            "angularUncertaintyDegrees":1,"lateralSupportM":10})
        template["recordSha256"]=hashlib.sha256(json.dumps(
            {k:v for k,v in template.items() if k!="recordSha256"},sort_keys=True,
            separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        with self.assertRaises(ValueError):evaluate_contact_orientation_hypotheses(template,{0:90})


if __name__=="__main__":unittest.main()
