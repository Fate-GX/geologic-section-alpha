import unittest
import numpy as np
from geologic_3d_engine.section.gaussian_ridge_surface import GaussianRidgeSurface


class GaussianRidgeSurfaceTests(unittest.TestCase):
    def test_affine_trend_is_exact(self):
        xy=np.array([[x,y] for y in (0,10,20) for x in (0,10,20)],float)
        p=np.column_stack((xy,15+.2*xy[:,0]-.3*xy[:,1]))
        model=GaussianRidgeSurface(p,2.0,.01)
        q=np.array([[3,7],[17,4]],float)
        np.testing.assert_allclose(model.evaluate(q),15+.2*q[:,0]-.3*q[:,1],atol=1e-11)

    def test_regularization_reduces_condition_number(self):
        xy=np.array([[x,y] for y in np.linspace(0,20,5) for x in np.linspace(0,20,7)],float)
        p=np.column_stack((xy,20+np.sin(xy[:,0]/4)+np.cos(xy[:,1]/5)))
        exact=GaussianRidgeSurface(p,1.0,0.0)
        ridge=GaussianRidgeSurface(p,1.0,.01)
        self.assertLess(ridge.condition_number,exact.condition_number)

    def test_gradient_matches_central_difference(self):
        xy=np.array([[x,y] for y in (0,10,20) for x in (0,10,20)],float)
        p=np.column_stack((xy,20+np.sin(xy[:,0]/5)+np.cos(xy[:,1]/7)))
        model=GaussianRidgeSurface(p,3.0,.01);q=np.array([[7.,9.],[13.,4.]])
        h=1e-5; numeric=[]
        for point in q:
            dx=np.array([[h,0.]]);dy=np.array([[0.,h]])
            numeric.append([(model.evaluate(point[None,:]+dx)[0]-model.evaluate(point[None,:]-dx)[0])/(2*h),
                            (model.evaluate(point[None,:]+dy)[0]-model.evaluate(point[None,:]-dy)[0])/(2*h)])
        np.testing.assert_allclose(model.gradient(q),numeric,rtol=1e-7,atol=1e-7)

    def test_invalid_inputs_reject(self):
        p=[[0,0,1],[1,0,2],[0,1,3]]
        for inverse,regularization in ((0,0),(True,0),(1,-1),(1,True)):
            with self.assertRaises(ValueError):GaussianRidgeSurface(p,inverse,regularization)


if __name__=="__main__":unittest.main()
