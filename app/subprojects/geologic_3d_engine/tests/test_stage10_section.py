import unittest
from pathlib import Path

from geologic_3d_engine.config import load_config
from geologic_3d_engine.events.event_spec import load_event_spec
from geologic_3d_engine.events.intrusion_spec import load_intrusion_spec
from geologic_3d_engine.geometry.mesh_spec import load_mesh_spec
from geologic_3d_engine.geometry.refinement_spec import load_refinement_spec
from geologic_3d_engine.physics.compaction_spec import load_compaction_spec
from geologic_3d_engine.physics.structural_spec import load_structural_spec
from geologic_3d_engine.section.section_spec import SectionSpec, load_section_spec
from geologic_3d_engine.section.plane_intersection import _assemble_loops
from geologic_3d_engine.section.uncertainty_projection import project_uncertainty_to_section
from geologic_3d_engine.stage10 import run_stage_ten, stage_ten_manifest
from geologic_3d_engine.stratigraphy.stack_spec import load_stack_spec
from geologic_3d_engine.uncertainty.ensemble_spec import load_ensemble_spec

ROOT=Path(__file__).resolve().parents[1]


class Stage10SectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        e=ROOT/"examples"
        cls.args=(load_config(e/"stage6_small_config.json"),load_stack_spec(e/"stage6_stack_spec.json"),
          load_event_spec(e/"stage3_event_spec.json"),load_compaction_spec(e/"stage6_compaction_spec.json"),
          load_structural_spec(e/"stage6_structural_spec.json"),load_intrusion_spec(e/"stage6_intrusion_spec.json"),
          load_mesh_spec(e/"stage7_mesh_spec.json"),load_refinement_spec(e/"stage8_refinement_spec.json"),
          load_ensemble_spec(e/"stage9_ensemble_spec.json"))
        cls.spec=load_section_spec(e/"stage10_section_spec.json")
        cls.result=run_stage_ten(*cls.args,cls.spec)

    def test_canonical_section_passes(self):
        self.assertTrue(self.result["passed"])

    def test_all_polygons_are_closed_and_positive_area(self):
        polygons=[p for u in self.result["section"]["unitSections"] for p in u["polygons"]]
        self.assertTrue(all(p["closed"] and p["area"]>0 for p in polygons))

    def test_declared_plane_basis_is_orthonormal(self):
        s=self.result["section"]; u,v,n=s["uDirection"],s["vDirection"],s["normal"]
        self.assertAlmostEqual(sum(a*b for a,b in zip(u,v)),0,places=12)
        self.assertAlmostEqual(sum(a*b for a,b in zip(u,n)),0,places=12)
        self.assertAlmostEqual(sum(a*b for a,b in zip(v,n)),0,places=12)

    def test_polygon_vertices_respect_declared_bounds(self):
        for unit in self.result["section"]["unitSections"]:
            for polygon in unit["polygons"]:
                for u,v in polygon["verticesUV"]:
                    self.assertTrue(self.spec.u_range[0]<=u<=self.spec.u_range[1])
                    self.assertTrue(self.spec.v_range[0]<=v<=self.spec.v_range[1])

    def test_zero_normal_is_rejected(self):
        bad=SectionSpec("bad",(0,0,0),(0,0,0),(1,0,0),(0,100),(-50,50))
        self.assertFalse(run_stage_ten(*self.args,bad)["passed"])

    def test_nonperpendicular_u_direction_is_rejected(self):
        bad=SectionSpec("bad",(0,0,0),(0,1,0),(1,1,0),(0,100),(-50,50))
        self.assertFalse(run_stage_ten(*self.args,bad)["passed"])

    def test_reversed_range_is_rejected(self):
        bad=SectionSpec("bad",(0,0,0),(0,1,0),(1,0,0),(100,0),(-50,50))
        self.assertFalse(run_stage_ten(*self.args,bad)["passed"])

    def test_coplanar_mesh_plane_is_rejected_as_ambiguous(self):
        bad=SectionSpec("domain_face",(0,0,0),(1,0,0),(0,1,0),(0,100),(-50,50))
        self.assertFalse(run_stage_ten(*self.args,bad)["passed"])

    def test_output_preserves_source_coordinate_frame(self):
        self.assertEqual(self.result["section"]["validation"]["coordinateFrame"],
                         "SourceMaterialGrid")

    def test_manifest_authorizes_export_contract(self):
        self.assertEqual(stage_ten_manifest(self.result)["nextAuthorizedStage"],
                         "autocad_export_contract")

    def test_stage9_spatial_uncertainty_is_projected(self):
        projected=self.result["uncertaintySection"]
        self.assertTrue(projected["validation"]["passed"])
        self.assertGreater(projected["validation"]["inDomainSampleCount"],0)
        self.assertEqual(self.result["modelSummary"]["uncertaintyProjection"],
                         "SectionAlignedSpatialGrid_NearestSourceCell")

    def test_projected_probabilities_remain_normalized(self):
        rows=self.result["uncertaintySection"]["materialProbabilityVU"]
        values=[p for row in rows for p in row if p is not None]
        self.assertTrue(values)
        self.assertTrue(all(abs(sum(p.values())-1.0)<=1e-12 for p in values))

    def test_out_of_domain_uncertainty_is_explicit(self):
        wide=SectionSpec("wide",self.spec.origin,self.spec.normal,self.spec.u_direction,
                         (-50.0,150.0),(-150.0,150.0),self.spec.tolerance)
        stage9=self.result["stageNine"];ensemble=stage9["ensemble"]
        projected=project_uncertainty_to_section(ensemble["materialProbabilityZYX"],
          ensemble["normalizedEntropyZYX"],ensemble["disagreementMaskZYX"],
          stage9["stageEight"]["adaptiveModel"].fine_grid,wide)
        self.assertGreater(projected["validation"]["outOfDomainSampleCount"],0)
        self.assertTrue(any(not value for row in projected["inDomainMaskVU"] for value in row))

    def test_uncertainty_projection_is_deterministic(self):
        again=run_stage_ten(*self.args,self.spec)["uncertaintySection"]
        self.assertEqual(self.result["uncertaintySection"],again)

    def test_invalid_probability_is_rejected_even_when_sum_is_one(self):
        stage9=self.result["stageNine"];ensemble=stage9["ensemble"]
        probability=[[ [dict(value) for value in row] for row in layer]
                     for layer in ensemble["materialProbabilityZYX"]]
        for layer in probability:
            for row in layer:
                for index in range(len(row)):row[index]={"A":1.1,"B":-0.1}
        projected=project_uncertainty_to_section(probability,ensemble["normalizedEntropyZYX"],
          ensemble["disagreementMaskZYX"],stage9["stageEight"]["adaptiveModel"].fine_grid,
          self.spec)
        self.assertFalse(projected["validation"]["passed"])
        self.assertTrue(any(e["code"]=="InvalidMaterialProbability"
                            for e in projected["validation"]["errors"]))

    def test_shape_mismatch_is_rejected(self):
        stage9=self.result["stageNine"];ensemble=stage9["ensemble"]
        with self.assertRaises(ValueError):
            project_uncertainty_to_section(ensemble["materialProbabilityZYX"][:-1],
              ensemble["normalizedEntropyZYX"],ensemble["disagreementMaskZYX"],
              stage9["stageEight"]["adaptiveModel"].fine_grid,self.spec)

    def test_sampling_spacing_policy_and_limit_are_explicit(self):
        projected=self.result["uncertaintySection"]
        self.assertEqual(projected["samplingSpacing"],
                         min(self.result["stageNine"]["stageEight"]["adaptiveModel"].fine_grid.cell_size))
        self.assertEqual(projected["samplingSpacingPolicy"],
                         "MinimumSourceCellEdge_NoInventedSubcellResolution")
        stage9=self.result["stageNine"];ensemble=stage9["ensemble"]
        with self.assertRaisesRegex(ValueError,"maximum is 1"):
            project_uncertainty_to_section(ensemble["materialProbabilityZYX"],
              ensemble["normalizedEntropyZYX"],ensemble["disagreementMaskZYX"],
              stage9["stageEight"]["adaptiveModel"].fine_grid,self.spec,maximum_samples=1)

    def test_no_intersection_is_a_typed_rejection(self):
        outside=SectionSpec("outside",(10000,10000,10000),self.spec.normal,
                            self.spec.u_direction,(0,10),(0,10),self.spec.tolerance)
        stage9=self.result["stageNine"];ensemble=stage9["ensemble"]
        projected=project_uncertainty_to_section(ensemble["materialProbabilityZYX"],
          ensemble["normalizedEntropyZYX"],ensemble["disagreementMaskZYX"],
          stage9["stageEight"]["adaptiveModel"].fine_grid,outside)
        self.assertEqual(projected["coverageStatus"],"NoIntersection")
        self.assertFalse(projected["validation"]["passed"])
        self.assertTrue(any(e["code"]=="SectionDoesNotIntersectUncertaintyGrid"
                            for e in projected["validation"]["errors"]))

    def test_declared_pinchout_triangle_remains_a_closed_loop(self):
        # A geometrically resolved pinch-out is a zero-thickness endpoint of a
        # closed wedge, not automatically a branched graph.
        segments=[((0.0,0.0),(2.0,0.0)),
                  ((2.0,0.0),(0.0,1.0)),
                  ((0.0,1.0),(0.0,0.0))]
        loops,errors=_assemble_loops(segments,1e-9)
        self.assertEqual(errors,[])
        self.assertEqual(len(loops),1)
        self.assertEqual(loops[0][0],loops[0][-1])

    def test_ambiguous_branched_graph_is_rejected_not_silently_paired(self):
        # Allowing degree-three vertices without a planar-arrangement policy
        # would make edge pairing order-dependent.
        segments=[((0.0,0.0),(1.0,0.0)),
                  ((0.0,0.0),(0.0,1.0)),
                  ((0.0,0.0),(-1.0,0.0))]
        loops,errors=_assemble_loops(segments,1e-9)
        self.assertEqual(loops,[])
        self.assertTrue(any(item["code"]=="OpenOrBranchedSectionGraph" and
                            item["degree"]==3 for item in errors))


if __name__=="__main__": unittest.main()
