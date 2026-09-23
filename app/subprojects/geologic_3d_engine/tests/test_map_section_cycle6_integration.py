import unittest
import numpy as np
from run_map_constrained_section_cycle6 import build_cycle6_model,SURFACES
from geologic_3d_engine.section.interlocking_sections import audit_section_intersection


class Cycle6IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        evaluate,cls.channel,cls.reference=build_cycle6_model()
        cls.evaluate=staticmethod(evaluate)

    def test_surface_family_is_ordered_over_full_plan_grid(self):
        x,y=np.meshgrid(np.linspace(0,600,41),np.linspace(0,520,37))
        q=np.column_stack((x.ravel(),y.ravel()))
        values=np.vstack([self.evaluate(s,q) for s in SURFACES])
        self.assertTrue(np.all(np.diff(values,axis=0)>=-1e-12))

    def test_channel_fill_is_zero_outside_and_matches_incision_inside(self):
        q=np.array([[300,420],[300,0],[0,0],[600,0]],float)
        incision=self.channel.surfaces(q)["incision"]
        fill=self.evaluate("UNCONFORMITY",q)-self.evaluate("CHANNEL_BED",q)
        np.testing.assert_allclose(fill,incision,atol=1e-12)
        self.assertTrue(np.any(incision>0));self.assertTrue(np.any(incision==0))

    def test_lower_and_upper_fill_partition_total_incision(self):
        q=np.array([[x,y] for y in np.linspace(0,520,17) for x in np.linspace(0,600,19)],float)
        bed=self.evaluate("CHANNEL_BED",q);split=self.evaluate("CHANNEL_SPLIT",q);top=self.evaluate("UNCONFORMITY",q)
        np.testing.assert_allclose((split-bed)+(top-split),top-bed,atol=1e-12)
        self.assertTrue(np.all(split>=bed));self.assertTrue(np.all(top>=split))

    def test_crossing_sections_use_identical_3d_values(self):
        result=audit_section_intersection(self.evaluate,SURFACES,[300,260],"EW","NS",0)
        self.assertTrue(result["passed"]);self.assertEqual(result["maximumAbsoluteResidual"],0)


if __name__=="__main__":unittest.main()
