import unittest
import numpy as np
from geologic_3d_engine.section.sampling_convergence import audit_section_sampling


class SamplingConvergenceTests(unittest.TestCase):
    def test_planar_surface_is_exact(self):
        evaluator=lambda sid,q:2*q[:,0]-q[:,1]+({"A":0,"B":3}[sid])
        result=audit_section_sampling(evaluator,["A","B"],[0,0],[10,7],[11,21,41],1e-10)
        self.assertTrue(result["passed"]);self.assertLess(result["finalMaximumDeviationM"],1e-12)

    def test_under_sampled_wave_fails_strict_gate(self):
        evaluator=lambda sid,q:np.sin(q[:,0]*3)
        result=audit_section_sampling(evaluator,["A"],[0,0],[10,0],[5,9,1001],.01)
        self.assertFalse(result["passed"])

    def test_invalid_policy_rejects(self):
        evaluator=lambda sid,q:np.zeros(len(q))
        for counts,tolerance in (([2,4],1),([5,4],1),([3],1),([3,5],True)):
            with self.assertRaises(ValueError):audit_section_sampling(evaluator,["A"],[0,0],[1,0],counts,tolerance)


if __name__=="__main__":unittest.main()
