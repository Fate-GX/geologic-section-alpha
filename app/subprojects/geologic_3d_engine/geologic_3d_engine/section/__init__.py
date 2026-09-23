"""Exact B-rep/plane section extraction."""

from .section_spec import SectionSpec, load_section_spec
from .plane_intersection import extract_section

__all__ = ["SectionSpec", "extract_section", "load_section_spec"]
from .map_template import (MeasuredRoute2D, RegularDem2D,
                           apparent_dip_degrees, build_section_template,
                           intersect_route_with_contacts)
from .orientation_geometry import (plane_from_three_points,
                                    plane_from_points_orthogonal_least_squares,
                                    planar_contact_on_vertical_section,
                                    strike_dip_from_normal)
from .rbf_structural_surface import RbfStructuralSurface
from .surface_family import ConformableSurfaceFamily, truncate_by_unconformity
from .borehole_constraints import validate_borehole_boundaries
from .borehole_evidence import screen_boreholes_to_geographic_route
from .route_evidence_readiness import assess_route_evidence_readiness
from .raster_evidence import assess_numeric_raster_evidence
from .resistivity_evidence import (schlumberger_apparent_resistivity,
                                   assess_resistivity_interpretation)
from .fault_displacement import VerticalThrowFault
from .interlocking_sections import audit_section_intersection
from .structural_uncertainty import leave_one_out_rbf
from .surface_ensemble import RbfSurfaceEnsemble
from .gaussian_ridge_surface import GaussianRidgeSurface
from .surface_model_selection import evaluate_surface_candidates

__all__ = ["MeasuredRoute2D", "RegularDem2D", "apparent_dip_degrees",
           "build_section_template", "intersect_route_with_contacts",
           "plane_from_three_points", "plane_from_points_orthogonal_least_squares",
           "planar_contact_on_vertical_section",
           "strike_dip_from_normal", "RbfStructuralSurface",
           "ConformableSurfaceFamily", "truncate_by_unconformity"]
__all__ += ["validate_borehole_boundaries", "assess_route_evidence_readiness",
            "assess_numeric_raster_evidence", "VerticalThrowFault",
            "audit_section_intersection", "screen_boreholes_to_geographic_route",
            "schlumberger_apparent_resistivity", "assess_resistivity_interpretation"]
__all__ += ["leave_one_out_rbf"]
__all__ += ["RbfSurfaceEnsemble"]
__all__ += ["GaussianRidgeSurface"]
__all__ += ["evaluate_surface_candidates"]
