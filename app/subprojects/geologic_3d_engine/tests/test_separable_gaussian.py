import pathlib,sys,unittest
import numpy as np
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from geologic_3d_engine.fields.separable_gaussian import (
 complexity_estimate,gaussian_axis_covariance,machine_eigen_tolerance,
 sample_separable_gaussian,separable_covariance)
def tolerances(nx,ny):return (machine_eigen_tolerance(nx),machine_eigen_tolerance(ny))

class SeparableGaussianTests(unittest.TestCase):
 def test_positive_exact_covariance_factorization(self):
  nx,ny=4,3;kx=gaussian_axis_covariance(nx,10,20);ky=gaussian_axis_covariance(ny,15,30)
  expected=2.5*np.kron(ky,kx);actual=separable_covariance(nx,ny,10,15,20,30,2.5)
  np.testing.assert_allclose(actual,expected,rtol=0,atol=0)
 def test_sampling_factor_reconstructs_covariance(self):
  nx,ny=3,2;kx=gaussian_axis_covariance(nx,10,20);ky=gaussian_axis_covariance(ny,10,15)
  lx,qx=np.linalg.eigh(kx);ly,qy=np.linalg.eigh(ky)
  factor=np.sqrt(1.7)*np.kron(qy@np.diag(np.sqrt(ly)),qx@np.diag(np.sqrt(lx)))
  np.testing.assert_allclose(factor@factor.T,separable_covariance(nx,ny,10,10,20,15,1.7),rtol=1e-12,atol=1e-12)
 def test_seeded_sample_is_exactly_reproducible(self):
  def run():
   z=np.random.default_rng(123).standard_normal((3,4))
   return sample_separable_gaussian(nx=4,ny=3,spacing_x=10,spacing_y=10,range_x=20,range_y=30,variance=1,standard_normal=z,negative_eigen_tolerances=tolerances(4,3))
  np.testing.assert_array_equal(run(),run())
 def test_boundary_zero_variance_is_zero(self):
  value=sample_separable_gaussian(nx=2,ny=2,spacing_x=1,spacing_y=1,range_x=2,range_y=2,variance=0,standard_normal=np.ones((2,2)),negative_eigen_tolerances=tolerances(2,2))
  np.testing.assert_array_equal(value,np.zeros((2,2)))
 def test_negative_variance_rejected(self):
  with self.assertRaisesRegex(ValueError,"non-negative"):separable_covariance(2,2,1,1,2,2,-1)
 def test_missing_wrong_noise_shape_rejected(self):
  with self.assertRaisesRegex(ValueError,"ny,nx"):sample_separable_gaussian(nx=2,ny=2,spacing_x=1,spacing_y=1,range_x=2,range_y=2,variance=1,standard_normal=np.ones((4,)),negative_eigen_tolerances=tolerances(2,2))
 def test_conflicting_nonfinite_noise_rejected(self):
  z=np.ones((2,2));z[0,0]=np.nan
  with self.assertRaisesRegex(ValueError,"finite"):sample_separable_gaussian(nx=2,ny=2,spacing_x=1,spacing_y=1,range_x=2,range_y=2,variance=1,standard_normal=z,negative_eigen_tolerances=tolerances(2,2))
 def test_out_of_scope_irregular_axis_rejected_by_contract(self):
  with self.assertRaisesRegex(ValueError,"positive"):gaussian_axis_covariance(3,0,2)
 def test_complexity_reduction_is_explicit(self):
  estimate=complexity_estimate(100,100)
  self.assertEqual(estimate["denseMatrixElements"],100_000_000)
  self.assertEqual(estimate["separableMatrixElements"],20_000)
  self.assertGreater(estimate["denseCubicWorkProxy"]/estimate["separableCubicWorkProxy"],100_000)
 def test_declared_tolerance_is_required_and_validated(self):
  z=np.ones((2,2))
  with self.assertRaisesRegex(ValueError,"tolerances"):
   sample_separable_gaussian(nx=2,ny=2,spacing_x=1,spacing_y=1,range_x=2,range_y=2,variance=1,standard_normal=z,negative_eigen_tolerances=(-1,1))
if __name__=="__main__":unittest.main()
