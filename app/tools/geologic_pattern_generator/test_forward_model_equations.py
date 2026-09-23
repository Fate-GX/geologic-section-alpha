import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from forward_model_equations import (
    badlands_linear_hillslope_rate, badlands_nonlinear_hillslope_flux_factor,
    badlands_sediment_flux_incision_factor,
    badlands_detachment_erosion_rate, badlands_transport_capacity,
    carbokitten_active_layer_step, carbokitten_equilibrium_active_layer,
    carbokitten_carbonate_production_rate, carbokitten_water_depth,
    classify_badlands_flux_state, linear_wave_celerity,
)


class ForwardModelEquationTests(unittest.TestCase):
    def test_badlands_published_power_laws(self):
        erosion = badlands_detachment_erosion_rate(2, 4, 9, .5, 0, .5, 1)
        self.assertAlmostEqual(erosion["value"], 6.0)
        capacity = badlands_transport_capacity(2, 4, 9, .5, .5, 1)
        self.assertAlmostEqual(capacity["value"], 6.0)

    def test_flux_regime_is_explicit(self):
        self.assertEqual(classify_badlands_flux_state(12, 6)["state"], "Depositional")
        self.assertEqual(classify_badlands_flux_state(3, 6)["state"], "DetachmentDominated")

    def test_carbokitten_depth_and_production(self):
        depth = carbokitten_water_depth(10, 4, 2)["value"]
        self.assertEqual(depth, 8)
        shallow = carbokitten_carbonate_production_rate(0, 100, 2, 1, .1)["value"]
        deep = carbokitten_carbonate_production_rate(20, 100, 2, 1, .1)["value"]
        self.assertGreater(shallow, deep)
        self.assertEqual(carbokitten_carbonate_production_rate(-1, 100, 2, 1, .1)["value"], 0)

    def test_negative_physical_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            badlands_transport_capacity(1, 1, -1, .1, .5, 1)

    def test_cover_laws_have_documented_character(self):
        self.assertAlmostEqual(badlands_sediment_flux_incision_factor(.5, "almost_parabolic")["value"], 1)
        self.assertAlmostEqual(badlands_sediment_flux_incision_factor(.35, "dynamic_cover")["value"], 1)
        self.assertAlmostEqual(badlands_sediment_flux_incision_factor(.5, "linear_decline")["value"], .5)

    def test_hillslope_and_wave_primitives(self):
        self.assertAlmostEqual(badlands_linear_hillslope_rate(.2, -3)["value"], -.6)
        self.assertGreater(badlands_nonlinear_hillslope_flux_factor(.7, .8)["value"], 1)
        with self.assertRaises(ValueError):
            badlands_nonlinear_hillslope_flux_factor(.8, .8)
        self.assertGreater(linear_wave_celerity(100, 10)["value"], 0)

    def test_carbokitten_lithification_equilibrium(self):
        step = carbokitten_active_layer_step(10, 100, 100, 0)["value"]
        self.assertAlmostEqual(step, 5)
        equilibrium = carbokitten_equilibrium_active_layer(2, 10)["value"]
        self.assertAlmostEqual(equilibrium, 20 / __import__("math").log(2))


if __name__ == "__main__":
    unittest.main()
