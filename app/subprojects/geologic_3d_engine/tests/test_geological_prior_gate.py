import unittest

from geologic_3d_engine.validation.geological_prior_gate import evaluate_geological_priors


class GeologicalPriorGateTests(unittest.TestCase):
    def test_universal_rules_are_evaluated_before_region(self):
        result = evaluate_geological_priors({"profileId": "R", "eventAuthorization": {
            "status": "NoRouteSpecificSubsurfaceEvidence",
            "requestedLocalizedEventTypes": [],
            "routeApplicableSubsurfaceSourceIds": []}})
        self.assertEqual(result["evaluationOrder"], ["Universal", "Regional"])
        self.assertTrue(result["universal"]["passed"])
        self.assertEqual(result["architectureMode"],
                         "ConservativeRegionalPrior_NoLocalizedEvents")
        self.assertFalse(result["localizedEventsAuthorized"])

    def test_named_region_does_not_authorize_a_major_event(self):
        result = evaluate_geological_priors({"profileId": "FAMOUS-REGION", "eventAuthorization": {
            "status": "SyntheticAssumption",
            "requestedLocalizedEventTypes": ["IncisedValley"],
            "routeApplicableSubsurfaceSourceIds": []}})
        self.assertTrue(result["safeDegradationApplied"])
        self.assertFalse(result["localizedEventsAuthorized"])

    def test_route_evidence_can_authorize_declared_event_class(self):
        result = evaluate_geological_priors({"profileId": "R", "eventAuthorization": {
            "status": "EvidenceBound",
            "requestedLocalizedEventTypes": ["IncisedValley"],
            "routeApplicableSubsurfaceSourceIds": ["BOREHOLE-1"]}})
        self.assertEqual(result["architectureMode"], "EvidenceBoundLocalizedEvents")
        self.assertTrue(result["localizedEventsAuthorized"])

    def test_missing_regional_authorization_contract_fails_closed(self):
        result = evaluate_geological_priors({"profileId": "R"})
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
