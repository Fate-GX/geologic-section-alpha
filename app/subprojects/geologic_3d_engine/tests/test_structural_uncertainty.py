import unittest
import numpy as np
from geologic_3d_engine.section.structural_uncertainty import leave_one_out_rbf


class StructuralUncertaintyTests(unittest.TestCase):
    def test_plane_leave_one_out_is_exact(self):
        xy=np.array([[x,y] for y in (0,10,20) for x in (0,10,20)],float)
        z=20+.3*xy[:,0]-.1*xy[:,1]
        result=leave_one_out_rbf(np.column_stack((xy,z)),.4,observation_sigma=np.full(len(xy),.2))
        self.assertTrue(result["passed"])
        self.assertLess(result["maximumAbsoluteResidual"],1e-10)
        self.assertEqual(result["uncertaintyMode"],"DeclaredObservationSigma")

    def test_outlier_is_detected_predictively(self):
        xy=np.array([[x,y] for y in (0,10,20) for x in (0,10,20)],float)
        z=20+.3*xy[:,0]-.1*xy[:,1]; z[4]+=8
        result=leave_one_out_rbf(np.column_stack((xy,z)),.4,observation_sigma=np.ones(len(xy)),
                                 maximum_standardized_residual=3)
        self.assertFalse(result["passed"])
        self.assertGreater(result["maximumAbsoluteStandardizedResidual"],3)

    def test_invalid_uncertainty_rejects(self):
        points=np.array([[0,0,0],[1,0,1],[0,1,1],[1,1,2],[2,2,4]],float)
        for sigma in ([1,1,1,1], [1,1,0,1,1], [1,1,True,1,1]):
            with self.assertRaises(ValueError): leave_one_out_rbf(points,.3,observation_sigma=sigma)


if __name__=="__main__": unittest.main()
