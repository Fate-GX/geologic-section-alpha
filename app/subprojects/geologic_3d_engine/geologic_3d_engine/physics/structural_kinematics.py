"""Adapter exposing the existing universal structural-kinematics foundation."""

from pathlib import Path
import sys

_TOOLS = Path(__file__).resolve().parents[4] / "tools" / "geologic_pattern_generator"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from universal_structural_kinematics import (  # noqa: E402,F401
    affine_map, apply_fault_operator, compact_support_attenuation,
    determinant_2x2, fault_displacement, numerical_deformation_gradient,
    validate_continuous_deformation, validate_structural_inputs)

__all__ = ["affine_map", "apply_fault_operator", "compact_support_attenuation",
           "determinant_2x2", "fault_displacement", "numerical_deformation_gradient",
           "validate_continuous_deformation", "validate_structural_inputs"]
