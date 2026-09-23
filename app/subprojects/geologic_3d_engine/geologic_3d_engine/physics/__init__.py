"""Evidence-gated physical transformations."""

from .compaction import (athy_porosity, bulk_thickness_from_solid,
                         classify_diagenetic_evidence, compact_stack,
                         solid_thickness, transform_thickness,
                         validate_compacted_stack)

__all__ = ["athy_porosity", "bulk_thickness_from_solid",
           "classify_diagenetic_evidence", "compact_stack", "solid_thickness",
           "transform_thickness", "validate_compacted_stack"]
