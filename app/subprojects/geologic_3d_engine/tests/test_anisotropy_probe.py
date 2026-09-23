import importlib.util
from pathlib import Path
import unittest
import numpy as np

spec = importlib.util.spec_from_file_location("probe",Path(__file__).resolve().parents[1]/"anisotropy_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def test_full_covariance_from_basis_responses(self):
        # Reconstruct the linear operator from its responses to unit impulses.
        # Compare all 144 covariance entries to physical-distance definition.
        shape = (2,2,3); spacing = [2,3,5]; ranges = [4,7,8]
        operator = []
        for k in range(12):
            impulse = np.zeros(12);impulse[k] = 1
            field,_ = probe.sample_field(impulse.reshape(shape),spacing,ranges)
            operator.append(field.ravel())
        operator = np.array(operator).T
        positions = np.array([(x*2,y*3,z*5) for z,y,x in np.ndindex(shape)])
        delta = (positions[:,None,:]-positions[None,:,:])/ranges
        expected = np.exp(-np.sum(delta**2,axis=2))
        np.testing.assert_allclose(operator@operator.T,expected,atol=2e-14,rtol=2e-14)

    def test_root_reconstruction_and_roundoff_audit(self):
        root,audit = probe.root_covariance(40,1,50)
        expected = np.exp(-((np.arange(40)[:,None]-np.arange(40)[None,:])/50)**2)
        np.testing.assert_allclose(root@root.T,expected,atol=1e-13)
        self.assertLessEqual(audit["negativeTolerance"],1e-10)

    def test_rank_fraction_and_ties(self):
        field = np.arange(100).reshape(4,5,5)
        result = probe.classify_exact_fraction(field,.3)
        self.assertEqual(int(result.sum()),30)
        np.testing.assert_array_equal(result,field>=70)
        with self.assertRaises(ValueError):
            probe.classify_exact_fraction(np.ones((3,3,3)),.3)

    def test_replay_anisotropy_and_input_preservation(self):
        noise = np.random.default_rng(811).normal(size=(3,4,8)); old = noise.copy()
        a,_ = probe.sample_field(noise,[1,1,1],[2,2,2])
        b,_ = probe.sample_field(noise,[1,1,1],[2,2,2])
        c,_ = probe.sample_field(noise,[1,1,1],[7,2,2])
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(noise,old)
        self.assertFalse(np.array_equal(a,c))
        self.assertEqual(probe.classify_exact_fraction(a,.3).sum(),probe.classify_exact_fraction(c,.3).sum())

    def test_invalid_inputs(self):
        for size,spacing,scale in ((0,1,1),(True,1,1),(300,1,1),(3,0,1),(3,1,float('nan'))):
            with self.subTest(case=(size,spacing,scale)), self.assertRaises(ValueError):
                probe.root_covariance(size,spacing,scale)
        for field in (np.ones((2,2)),np.full((2,2,2),np.inf)):
            with self.assertRaises(ValueError):
                probe.sample_field(field,[1,1,1],[1,1,1])


if __name__=="__main__":
    unittest.main()
