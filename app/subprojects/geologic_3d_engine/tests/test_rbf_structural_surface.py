import unittest
import numpy as np

from geologic_3d_engine.section.rbf_structural_surface import RbfStructuralSurface


class RbfStructuralSurfaceTests(unittest.TestCase):
    def test_plane_is_reproduced_and_holdout_is_correct(self):
        xy=np.array([[0,0],[10,0],[0,10],[10,10],[5,3]],dtype=float)
        z=30+.2*xy[:,0]-.35*xy[:,1]
        model=RbfStructuralSurface(np.column_stack((xy,z)),.4)
        query=np.array([[2,8],[7,6],[4,4]],dtype=float)
        np.testing.assert_allclose(model.evaluate(query),30+.2*query[:,0]-.35*query[:,1],atol=1e-11)

    def test_curved_surface_honours_training_points(self):
        xy=np.array([[x,y] for y in (0,10,20) for x in (0,10,20)],dtype=float)
        z=50+4*np.sin(xy[:,0]/10)-3*np.cos(xy[:,1]/12)
        xyz=np.column_stack((xy,z))
        model=RbfStructuralSurface(xyz,.25)
        self.assertTrue(model.audit(xyz,1e-9)["passed"])

    def test_regularization_is_explicitly_approximate(self):
        xy=np.array([[0,0],[10,0],[0,10],[10,10]],dtype=float)
        xyz=np.column_stack((xy,[1,2,3,5]))
        exact=RbfStructuralSurface(xyz,.5,0)
        smooth=RbfStructuralSurface(xyz,.5,.1)
        self.assertLess(np.max(np.abs(exact.residuals(xyz))),1e-10)
        self.assertGreater(np.max(np.abs(smooth.residuals(xyz))),0)

    def test_invalid_or_ambiguous_controls_reject(self):
        bad=[[[0,0,1],[0,0,2],[1,1,3]], [[0,0,1],[1,0,2],[2,0,3]]]
        for points in bad:
            with self.assertRaises(ValueError): RbfStructuralSurface(points,.5)
        with self.assertRaises(ValueError): RbfStructuralSurface([[0,0,1],[1,0,2],[0,1,3]],0)


if __name__=="__main__": unittest.main()
