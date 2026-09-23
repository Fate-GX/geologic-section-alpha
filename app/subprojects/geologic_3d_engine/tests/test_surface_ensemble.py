import unittest
import numpy as np
from geologic_3d_engine.section.surface_ensemble import RbfSurfaceEnsemble


class SurfaceEnsembleTests(unittest.TestCase):
    def setUp(self):
        xy=np.array([[x,y] for y in (0,10,20) for x in (0,10,20)],float)
        self.points=np.column_stack((xy,30+.2*xy[:,0]-.1*xy[:,1]))

    def test_deterministic_and_quantiles_ordered(self):
        a=RbfSurfaceEnsemble(self.points,np.full(9,.5),.4,31,823)
        b=RbfSurfaceEnsemble(self.points,np.full(9,.5),.4,31,823)
        query=np.array([[2,3],[8,15],[19,6]],float)
        av=a.evaluate(query); bv=b.evaluate(query)
        np.testing.assert_array_equal(av["samples"],bv["samples"])
        self.assertTrue(np.all(np.diff(av["values"],axis=0)>=0))
        self.assertEqual(av["uncertaintyMeaning"],"ObservationZPerturbationSensitivity_NotPosterior")

    def test_seed_changes_realization_not_contract(self):
        a=RbfSurfaceEnsemble(self.points,np.full(9,.3),.4,7,1)
        b=RbfSurfaceEnsemble(self.points,np.full(9,.3),.4,7,2)
        self.assertFalse(np.array_equal(a.perturbations,b.perturbations))
        self.assertTrue(a.audit()["sharedSurfacePerMember"])

    def test_invalid_inputs_reject(self):
        bad_sigma=([1]*8,[1]*8+[0],[1]*8+[True])
        for sigma in bad_sigma:
            with self.assertRaises(ValueError):RbfSurfaceEnsemble(self.points,sigma,.4,5,1)
        for count in (True,2,3.5):
            with self.assertRaises(ValueError):RbfSurfaceEnsemble(self.points,[1]*9,.4,count,1)
        model=RbfSurfaceEnsemble(self.points,[1]*9,.4,3,1)
        for quantiles in ([.9,.1],[-.1,.5],[.5,1.1],[True]):
            with self.assertRaises(ValueError):model.evaluate([[1,1]],quantiles)


if __name__=="__main__":unittest.main()
