import unittest
from geologic_3d_engine.section.contact_structural_binding import (accept_unique_contact_bindings,
    propose_contact_structural_bindings)
from geologic_3d_engine.section.contact_orientation_hypothesis import build_contact_orientation_hypothesis_template
from geologic_3d_engine.section.route_binding import build_route_binding
from tests.test_contact_orientation_hypothesis import intersections


class ContactStructuralBindingTests(unittest.TestCase):
    def setUp(self):
        self.route=[[131,32.8],[131.01,32.8]];self.intersections=intersections()
        self.template=build_contact_orientation_hypothesis_template(self.intersections)
    def projected(self,observations):
        return {"schemaVersion":"StructuralObservationProjection-1.0",
            "routeBinding":build_route_binding(self.route),"observations":observations}
    def test_explicit_feature_binding_can_be_deliberately_accepted(self):
        obs={"observationId":"S1","sourceId":"FIELD-1","stationM":110,
            "projectionState":"Projected","appliesToFeatureIds":["C1"],"trueDipDegrees":25,
            "dipDirectionDegrees":120,"angularUncertaintyDegrees":4,"lateralSupportM":300}
        proposals=propose_contact_structural_bindings(self.route,self.intersections,self.template,self.projected([obs]),50)
        self.assertEqual(proposals["uniqueCandidateCount"],1)
        result=accept_unique_contact_bindings(self.template,proposals,["CONTACT-ORIENTATION-0000"])
        self.assertEqual(result["hypotheses"][0]["orientationBasis"],"EvidenceCandidate")
        self.assertFalse(result["hypotheses"][0]["subsurfaceContinuationAuthorized"])
    def test_nearness_alone_never_binds_and_ambiguity_never_auto_resolves(self):
        base={"sourceId":"FIELD","stationM":100,"projectionState":"Projected",
            "trueDipDegrees":20,"dipDirectionDegrees":90,"angularUncertaintyDegrees":2,"lateralSupportM":100}
        near={**base,"observationId":"N"}
        result=propose_contact_structural_bindings(self.route,self.intersections,self.template,self.projected([near]),50)
        self.assertEqual(result["uniqueCandidateCount"],0)
        a={**base,"observationId":"A","appliesToFeatureIds":["C1"]};b={**a,"observationId":"B"}
        result=propose_contact_structural_bindings(self.route,self.intersections,self.template,self.projected([a,b]),50)
        self.assertEqual(result["proposals"][0]["status"],"AmbiguousMultipleCandidates")
        with self.assertRaises(ValueError):accept_unique_contact_bindings(self.template,result,["CONTACT-ORIENTATION-0000"])
    def test_route_mismatch_rejects(self):
        with self.assertRaises(ValueError):propose_contact_structural_bindings(self.route,self.intersections,self.template,
            {"routeBinding":build_route_binding([[130,32],[131,32]]),"observations":[]},50)
