"""Compatibility exports for the canonical 3D-engine compaction module."""

from pathlib import Path
import sys

_SUBPROJECT = Path(__file__).resolve().parents[2] / "subprojects" / "geologic_3d_engine"
if str(_SUBPROJECT) not in sys.path:
    sys.path.insert(0, str(_SUBPROJECT))

from geologic_3d_engine.physics.compaction import (  # noqa: E402,F401
    athy_porosity, bulk_thickness_from_solid, classify_diagenetic_evidence,
    compact_stack, solid_thickness, transform_thickness, validate_compacted_stack)

__all__ = ["athy_porosity", "bulk_thickness_from_solid",
           "classify_diagenetic_evidence", "compact_stack", "solid_thickness",
           "transform_thickness", "validate_compacted_stack"]
