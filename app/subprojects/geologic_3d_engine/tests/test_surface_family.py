import unittest
import numpy as np

from geologic_3d_engine.section.rbf_structural_surface import RbfStructuralSurface
from geologic_3d_engine.section.surface_family import ConformableSurfaceFamily,truncate_by_unconformity


class SurfaceFamilyTests(unittest.TestCase):
    def setUp(self):
        xy=np.array([[0,0],[10,0],[0,10],[10,10]],float)
        z=20+.75*xy[:,0]
        self.surface=RbfStructuralSurface(np.column_stack((xy,z)),.5)

    def test_gradient_matches_plane(self):
        gradient=self.surface.gradient([[2,3],[8,7]])
        np.testing.assert_allclose(gradient,[[.75,0],[.75,0]],atol=1e-11)

    def test_true_thickness_converts_to_vertical_separation(self):
        family=ConformableSurfaceFamily(self.surface,[{"unitId":"A","trueThickness":lambda xy:np.full(len(xy),8.)}])
        result=family.evaluate([[2,3],[8,7]])
        np.testing.assert_allclose(result["units"][0]["verticalThickness"],[10,10],atol=1e-10)
        np.testing.assert_allclose(result["contactElevations"][1]-result["contactElevations"][0],[10,10])

    def test_variable_positive_thickness_and_unconformity(self):
        field=lambda xy:5+.1*xy[:,0]
        family=ConformableSurfaceFamily(self.surface,[{"unitId":"A","trueThickness":field}])
        result=family.evaluate([[0,0],[10,0]])
        self.assertEqual(result["minimumTrueThickness"],5)
        cut=truncate_by_unconformity(result["contactElevations"],[19,100])
        self.assertFalse(cut["activeMasks"][0][0]); self.assertTrue(cut["activeMasks"][0][1])

    def test_nonpositive_thickness_rejects(self):
        family=ConformableSurfaceFamily(self.surface,[{"unitId":"A","trueThickness":lambda xy:np.zeros(len(xy))}])
        with self.assertRaises(ValueError): family.evaluate([[1,1]])


if __name__=="__main__":unittest.main()
