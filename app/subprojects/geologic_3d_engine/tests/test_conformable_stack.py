import json
import pathlib
import sys
import unittest

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from geologic_3d_engine.config import load_config
from geologic_3d_engine.geometry.regular_grid import RegularGrid3D
from geologic_3d_engine.models import Extent3D
from geologic_3d_engine.stage2 import run_stage_two, stage_two_manifest
from geologic_3d_engine.stratigraphy.conformable_stack import (
    build_conformable_stack, voxelize_stack)
from geologic_3d_engine.stratigraphy.stack_spec import StackBuildSpec, load_stack_spec


CONFIG = root / "examples" / "stage2_small_config.json"
SPEC = root / "examples" / "stage2_stack_spec.json"


class ConformableStackTests(unittest.TestCase):
    def grid(self):
        return RegularGrid3D.from_extent(Extent3D((0, 0, -50), (100, 100, 50),
                                                   (50, 50, 10)))

    def test_regular_grid_requires_integral_cell_counts(self):
        with self.assertRaises(ValueError):
            RegularGrid3D.from_extent(Extent3D((0, 0, 0), (101, 100, 100),
                                                (50, 50, 10)))

    def test_shared_contacts_are_exact_objects(self):
        stack = build_conformable_stack(self.grid(), [[40, 40], [40, 40]],
                                        ["U1", "U2"],
                                        [[[20, 20], [20, 20]], [[10, 10], [10, 10]]])
        self.assertIs(stack.layers[0].bottom, stack.layers[1].top)
        self.assertTrue(stack.validate()["passed"])

    def test_negative_thickness_is_rejected(self):
        with self.assertRaises(ValueError):
            build_conformable_stack(self.grid(), [[40, 40], [40, 40]], ["U1"],
                                    [[[20, -1], [20, 20]]])

    def test_field_shape_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            build_conformable_stack(self.grid(), [[40]], ["U1"], [[[20]]])

    def test_zero_thickness_is_explicit_inactive_state(self):
        stack = build_conformable_stack(self.grid(), [[40, 40], [40, 40]], ["U1"],
                                        [[[0, 10], [10, 10]]])
        self.assertFalse(stack.layers[0].active[0][0])
        self.assertEqual(stack.layers[0].top[0][0], stack.layers[0].bottom[0][0])

    def test_layer_outside_vertical_extent_is_rejected(self):
        with self.assertRaises(ValueError):
            build_conformable_stack(self.grid(), [[40, 40], [40, 40]], ["U1"],
                                    [[[100, 100], [100, 100]]])

    def test_voxel_partition_has_no_overlap_or_void(self):
        result = run_stage_two(load_config(CONFIG), load_stack_spec(SPEC))
        self.assertTrue(result["passed"])
        voxel = result["voxelization"]
        self.assertEqual(voxel["overlapCount"], 0)
        self.assertEqual(voxel["envelopeVoidCount"], 0)
        self.assertEqual(voxel["unitCellCounts"], {"U1": 8, "U2": 10})

    def test_unit_volume_is_cell_count_times_cell_volume(self):
        result = run_stage_two(load_config(CONFIG), load_stack_spec(SPEC))
        self.assertEqual(result["voxelization"]["unitGeometricVolumes"]["U1"], 200000)
        self.assertEqual(result["voxelization"]["unitGeometricVolumes"]["U2"], 225000)
        self.assertEqual(result["voxelization"]["unitVoxelizedVolumes"]["U2"], 250000)
        self.assertEqual(result["voxelization"]["volumeDiscretizationError"]["U2"], 25000)

    def test_stack_order_must_match_configured_stratigraphy(self):
        data = json.loads(SPEC.read_text(encoding="utf-8"))
        data["layers"].reverse()
        result = run_stage_two(load_config(CONFIG), StackBuildSpec.from_dict(data))
        self.assertFalse(result["passed"])
        self.assertEqual(result["errors"][0]["code"], "StackConstructionFailed")

    def test_missing_thickness_field_is_rejected(self):
        data = json.loads(SPEC.read_text(encoding="utf-8"))
        data["layers"][0].pop("thicknessField")
        with self.assertRaisesRegex(ValueError, "values shape"):
            StackBuildSpec.from_dict(data).build(load_config(CONFIG))

    def test_constant_and_values_conflict_is_rejected(self):
        data = json.loads(SPEC.read_text(encoding="utf-8"))
        data["layers"][0]["thicknessField"]["values"] = [[20, 20], [20, 20]]
        with self.assertRaisesRegex(ValueError, "cannot define both"):
            StackBuildSpec.from_dict(data).build(load_config(CONFIG))

    def test_unsupported_covariance_model_is_rejected(self):
        data = json.loads(SPEC.read_text(encoding="utf-8"))
        data["layers"][0]["thicknessField"]["covarianceModel"] = {
            "type": "Gaussian", "range": 100
        }
        with self.assertRaisesRegex(ValueError, "unsupported keys: covarianceModel"):
            StackBuildSpec.from_dict(data).build(load_config(CONFIG))

    def test_stage_two_manifest_authorizes_stage_three_only_after_pass(self):
        result = run_stage_two(load_config(CONFIG), load_stack_spec(SPEC))
        manifest = stage_two_manifest(result)
        self.assertTrue(manifest["geometryGenerated"])
        self.assertEqual(manifest["nextAuthorizedStage"], "erosion_onlap_lens_pinchout")


if __name__ == "__main__":
    unittest.main()
