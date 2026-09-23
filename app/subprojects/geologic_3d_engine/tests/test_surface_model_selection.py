import unittest
import numpy as np
from geologic_3d_engine.section.surface_model_selection import evaluate_surface_candidates


class SurfaceModelSelectionTests(unittest.TestCase):
    def setUp(self):
        xy=np.array([[x,y] for y in np.linspace(0,20,5) for x in np.linspace(0,20,7)],float)
        self.points=np.column_stack((xy,20+2*np.sin(xy[:,0]/7)+np.cos(xy[:,1]/8)))
        self.query=np.array([[x,10] for x in np.linspace(0,20,21)],float)
        self.candidates=[
          {"modelId":"MQ","family":"MultiquadricAffine","shape":.8,"regularization":0.0},
          {"modelId":"GR","family":"GaussianAffineRidge","shape":3.0,"regularization":.1}]

    def test_selection_is_deterministic_and_requires_all_gates(self):
        gates={"maximumLooStandardizedResidual":10,"maximumConditionNumber":1e5,"maximumEnvelopeWidthM":10}
        a=evaluate_surface_candidates(self.points,[1]*35,self.query,self.candidates,11,42,gates)
        b=evaluate_surface_candidates(self.points,[1]*35,self.query,self.candidates,11,42,gates)
        self.assertEqual(a,b);self.assertTrue(a["passed"])
        selected=a["selected"]
        self.assertTrue(all(selected["checks"].values()))

    def test_no_candidate_passes_is_typed_rejection(self):
        gates={"maximumLooStandardizedResidual":1e-8,"maximumConditionNumber":2,"maximumEnvelopeWidthM":1e-8}
        result=evaluate_surface_candidates(self.points,[1]*35,self.query,self.candidates,7,1,gates)
        self.assertFalse(result["passed"]);self.assertIsNone(result["selectedModelId"])

    def test_unknown_family_and_bad_gate_reject(self):
        gates={"maximumLooStandardizedResidual":10,"maximumConditionNumber":1e5,"maximumEnvelopeWidthM":10}
        bad=[{"modelId":"X","family":"Secret","shape":1.0,"regularization":0.0}]
        with self.assertRaises(ValueError):evaluate_surface_candidates(self.points,[1]*35,self.query,bad,7,1,gates)
        with self.assertRaises(ValueError):evaluate_surface_candidates(self.points,[1]*35,self.query,self.candidates,7,1,{**gates,"maximumConditionNumber":True})


if __name__=="__main__":unittest.main()
