import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from universal_structural_kinematics import (
    affine_map, apply_fault_operator, compact_support_attenuation,
    validate_continuous_deformation, validate_structural_inputs,
)


class UniversalStructuralKinematicsTests(unittest.TestCase):
    def test_rigid_rotation_preserves_distance(self):
        mapped = affine_map([(0, 0), (3, 4)], [[0, -1], [1, 0]])
        self.assertAlmostEqual(math.dist(*mapped), 5)

    def test_orientation_reversal_is_rejected(self):
        with self.assertRaises(ValueError):
            affine_map([(0, 0)], [[1, 0], [0, -1]])

    def test_fault_operator_displaces_all_boundaries_consistently(self):
        lines = [[(1, 0), (1, 1)], [(1, 2), (1, 3)]]
        moved = apply_fault_operator(lines, lambda point: point[0], (0, 1), 5)
        for before, after in zip(lines, moved):
            for source, target in zip(before, after):
                self.assertEqual(target[1] - source[1], 5)

    def test_finite_fault_attenuation_reaches_zero_at_extent(self):
        self.assertEqual(compact_support_attenuation(10, 10), 0)
        self.assertGreater(compact_support_attenuation(0, 10), 0)

    def test_positive_jacobian_map_passes(self):
        report = validate_continuous_deformation(
            lambda point: (point[0], point[1] + 0.1 * math.sin(point[0])),
            [(0, 0), (1, 1), (2, 2)])
        self.assertTrue(report["passed"])

    def test_collapsing_map_fails(self):
        report = validate_continuous_deformation(lambda point: (point[0], 0), [(0, 0)])
        self.assertFalse(report["passed"])

    def test_missing_fault_kinematics_blocks_generation(self):
        report = validate_structural_inputs({"eventType": "Fault", "faultSurface": "F1"})
        self.assertFalse(report["geometryGenerationAuthorized"])


if __name__ == "__main__":
    unittest.main()
