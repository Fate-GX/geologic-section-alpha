import math
import pathlib
import sys
import unittest
import numpy as np

root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from geologic_3d_engine.fields.separable_gaussian import (
 machine_eigen_tolerance,sample_separable_gaussian,separable_covariance)
from geologic_3d_engine.fields.statistical_oracles import positive_part_normal_moment

NX,NY=3,2
VARIANCE=1.2
THRESHOLD=0.3
MU=2.0
BETA=1.5
SAMPLES=12000

def normal_positive_part_moment(power):
 return positive_part_normal_moment(variance=VARIANCE,threshold=THRESHOLD,power=power)

class StochasticStatisticsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  rng=np.random.default_rng(20260831);values=[];tol=(machine_eigen_tolerance(NX),machine_eigen_tolerance(NY))
  for _ in range(SAMPLES):
   values.append(sample_separable_gaussian(nx=NX,ny=NY,spacing_x=10,spacing_y=15,range_x=25,range_y=30,variance=VARIANCE,standard_normal=rng.standard_normal((NY,NX)),negative_eigen_tolerances=tol).reshape(-1))
  cls.latent=np.asarray(values);cls.target=separable_covariance(NX,NY,10,15,25,30,VARIANCE)
 def test_latent_mean_converges_with_six_sigma_bound(self):
  tolerance=6*math.sqrt(VARIANCE/SAMPLES)
  self.assertLess(float(np.max(np.abs(np.mean(self.latent,axis=0)))),tolerance)
 def test_latent_covariance_converges_with_six_sigma_bound(self):
  empirical=np.cov(self.latent,rowvar=False,ddof=1)
  standard=np.sqrt((VARIANCE**2+self.target**2)/(SAMPLES-1))
  self.assertLess(float(np.max(np.abs(empirical-self.target)/(standard+1e-30))),6.0)
 def test_zero_thickness_probability_converges(self):
  marginal=self.latent[:,0];observed=float(np.mean(marginal<=THRESHOLD));expected=0.5*(1+math.erf(THRESHOLD/math.sqrt(2*VARIANCE)))
  tolerance=6*math.sqrt(expected*(1-expected)/SAMPLES)
  self.assertLess(abs(observed-expected),tolerance)
 def test_transformed_mean_converges_to_quadrature(self):
  transformed=MU*np.maximum(self.latent[:,0]-THRESHOLD,0.0)**BETA
  expected=MU*normal_positive_part_moment(BETA)
  second=MU**2*normal_positive_part_moment(2*BETA);standard=math.sqrt((second-expected**2)/SAMPLES)
  self.assertLess(abs(float(np.mean(transformed))-expected),6*standard)
 def test_fixed_validation_seed_is_exactly_reproducible(self):
  rng=np.random.default_rng(20260831);tol=(machine_eigen_tolerance(NX),machine_eigen_tolerance(NY))
  first=sample_separable_gaussian(nx=NX,ny=NY,spacing_x=10,spacing_y=15,range_x=25,range_y=30,variance=VARIANCE,standard_normal=rng.standard_normal((NY,NX)),negative_eigen_tolerances=tol)
  np.testing.assert_array_equal(first,self.latent[0].reshape((NY,NX)))
 def test_adaptive_oracle_matches_independently_established_reference(self):
  expected=0.3258576372268814
  self.assertAlmostEqual(normal_positive_part_moment(BETA),expected,places=10)
 def test_old_100_point_hermite_bias_is_detected(self):
  nodes,weights=np.polynomial.hermite.hermgauss(100);old=float(np.sum(weights*np.maximum(np.sqrt(2*VARIANCE)*nodes-THRESHOLD,0.0)**BETA)/np.sqrt(np.pi))
  self.assertGreater(abs(old-normal_positive_part_moment(BETA)),5e-4)
 def test_integer_power_oracle_matches_half_second_moment(self):
  value=positive_part_normal_moment(variance=VARIANCE,threshold=0.0,power=2.0)
  self.assertAlmostEqual(value,VARIANCE/2,places=10)
 def test_linear_positive_part_matches_closed_form(self):
  value=positive_part_normal_moment(variance=VARIANCE,threshold=0.0,power=1.0)
  self.assertAlmostEqual(value,math.sqrt(VARIANCE/(2*math.pi)),places=10)
if __name__=="__main__":unittest.main()
