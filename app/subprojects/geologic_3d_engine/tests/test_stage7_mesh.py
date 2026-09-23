import unittest
from pathlib import Path

from geologic_3d_engine.config import load_config
from geologic_3d_engine.events.event_spec import load_event_spec
from geologic_3d_engine.events.intrusion_spec import load_intrusion_spec
from geologic_3d_engine.geometry.mesh_spec import MeshBuildSpec, load_mesh_spec
from geologic_3d_engine.geometry.regular_grid import RegularGrid3D
from geologic_3d_engine.geometry.voxel_brep import build_closed_breps,analyze_unit_components
from geologic_3d_engine.geometry.voxel_topology_audit import audit_unit_cells
from geologic_3d_engine.models import Extent3D
from geologic_3d_engine.physics.compaction_spec import load_compaction_spec
from geologic_3d_engine.physics.structural_spec import load_structural_spec
from geologic_3d_engine.stage7 import run_stage_seven, stage_seven_manifest
from geologic_3d_engine.stratigraphy.stack_spec import load_stack_spec

ROOT=Path(__file__).resolve().parents[1]


class Stage7MeshTests(unittest.TestCase):
    def setUp(self):
        e=ROOT/"examples"
        self.args=(load_config(e/"stage6_small_config.json"),load_stack_spec(e/"stage6_stack_spec.json"),
          load_event_spec(e/"stage3_event_spec.json"),load_compaction_spec(e/"stage6_compaction_spec.json"),
          load_structural_spec(e/"stage6_structural_spec.json"),load_intrusion_spec(e/"stage6_intrusion_spec.json"))
        self.spec=load_mesh_spec(e/"stage7_mesh_spec.json")

    def test_canonical_breps_are_closed_oriented_and_manifold(self):
        result=run_stage_seven(*self.args,self.spec); self.assertTrue(result["passed"])
        for mesh in result["brepModel"].unit_meshes:
            self.assertTrue(mesh.validation["closed"]); self.assertTrue(mesh.validation["oriented"])
            self.assertTrue(mesh.validation["manifold"])

    def test_mesh_volume_matches_voxel_volume(self):
        result=run_stage_seven(*self.args,self.spec)
        for mesh in result["brepModel"].unit_meshes:
            self.assertAlmostEqual(mesh.validation["volumeDifference"],0.0,places=8)

    def test_single_voxel_has_expected_boundary(self):
        grid=RegularGrid3D.from_extent(Extent3D((0,0,0),(1,1,1),(1,1,1)))
        mesh=build_closed_breps([[['U']]],grid,['U']).unit_meshes[0]
        self.assertEqual(len(mesh.quads),6); self.assertEqual(len(mesh.triangles),12)
        self.assertEqual(len(mesh.vertices),8)

    def test_adjacent_voxels_remove_internal_face(self):
        grid=RegularGrid3D.from_extent(Extent3D((0,0,0),(2,1,1),(1,1,1)))
        mesh=build_closed_breps([[['U','U']]],grid,['U']).unit_meshes[0]
        self.assertEqual(len(mesh.quads),10)

    def test_disconnected_bodies_are_counted(self):
        grid=RegularGrid3D.from_extent(Extent3D((0,0,0),(3,1,1),(1,1,1)))
        mesh=build_closed_breps([[['U',None,'U']]],grid,['U']).unit_meshes[0]
        self.assertEqual(mesh.connected_component_count,2); self.assertTrue(mesh.validation["passed"])

    def test_edge_touching_components_are_diagnosed_as_nonmanifold(self):
        grid=RegularGrid3D.from_extent(Extent3D((0,0,0),(2,2,1),(1,1,1)))
        mesh=build_closed_breps([[['U',None],[None,'U']]],grid,['U']).unit_meshes[0]
        self.assertEqual(mesh.connected_component_count,2)
        self.assertEqual(mesh.validation["openEdgeCount"],0)
        self.assertEqual(mesh.validation["nonManifoldEdgeCount"],1)
        edge=mesh.validation["problemEdgeDetails"][0]
        self.assertEqual(edge["useCount"],4);self.assertEqual(len(edge["faceIds"]),4)
        self.assertEqual(len(edge["sourceVoxels"]),4)
        self.assertEqual(edge["contactScope"],"InterComponentContact")
        self.assertEqual(len(edge["sourceComponentIds"]),2)
        self.assertEqual(len(edge["sourceFaceNormals"]),4)

    def test_edge_touching_components_are_individually_manifold_shells(self):
        grid=RegularGrid3D.from_extent(Extent3D((0,0,0),(2,2,1),(1,1,1)))
        result=analyze_unit_components([[['U',None],[None,'U']]],grid,'U')
        self.assertEqual(result["componentCount"],2);self.assertTrue(result["allComponentsManifold"])
        self.assertEqual(result["relations"][0]["relation"],"TouchEdge")
        self.assertEqual(result["relations"][0]["sharedVertexCount"],2)

    def test_separated_components_are_disjoint_manifold_shells(self):
        grid=RegularGrid3D.from_extent(Extent3D((0,0,0),(3,1,1),(1,1,1)))
        result=analyze_unit_components([[['U',None,'U']]],grid,'U')
        self.assertTrue(result["allComponentsManifold"]);self.assertEqual(result["relations"][0]["relation"],"Disjoint")

    def test_five_voxel_global_minima_are_preflight_intra_component_contacts(self):
        solutions=(((11,14,52),(11,15,51),(11,15,52),(12,14,51),(12,14,52)),((11,15,51),(11,15,52),(12,14,51),(12,14,52),(12,15,52)))
        for cells in solutions:
            audit=audit_unit_cells(cells,'U');self.assertEqual(audit["componentCount"],1);self.assertEqual(audit["touchEdgeCount"],1);self.assertEqual(audit["contacts"][0]["classification"],"IntraComponentTouchEdge")

    def test_filled_diagonal_bridge_is_not_flagged(self):
        self.assertTrue(audit_unit_cells(((0,0,0),(1,0,0),(0,1,0),(1,1,0)),'U')["passed"])

    def test_body_diagonal_voxels_are_inter_component_point_contact(self):
        audit=audit_unit_cells(((0,0,0),(1,1,1)),'U');self.assertEqual(audit["touchEdgeCount"],0);self.assertEqual(audit["touchPointCount"],1);self.assertEqual(audit["contacts"][0]["classification"],"InterComponentTouchPoint")

    def test_vertex_link_mesh_audit_closes_point_contact_gap(self):
        grid=RegularGrid3D.from_extent(Extent3D((0,0,0),(2,2,2),(1,1,1)))
        mesh=build_closed_breps([[['U',None],[None,None]],[[None,None],[None,'U']]],grid,['U']).unit_meshes[0]
        self.assertFalse(mesh.validation["passed"]);self.assertFalse(mesh.validation["manifold"])
        self.assertEqual(mesh.validation["nonManifoldVertexCount"],1)
        self.assertEqual(mesh.validation["problemVertexDetails"][0]["linkComponentCount"],2)
        self.assertTrue(any(e["code"]=="NonManifoldVertex" for e in mesh.validation["errors"]))
        self.assertFalse(audit_unit_cells(((0,0,0),(1,1,1)),'U')["passed"])

    def test_degree_four_vertex_link_fixture_is_permanent(self):
        grid=RegularGrid3D.from_extent(Extent3D((0,0,0),(2,2,2),(1,1,1)))
        labels=[[['U',None],[None,'U']],[[None,None],[None,'U']]]
        mesh=build_closed_breps(labels,grid,['U']).unit_meshes[0]
        self.assertFalse(mesh.validation["passed"])
        self.assertEqual(mesh.validation["nonManifoldEdgeCount"],1)
        self.assertEqual(mesh.validation["nonManifoldVertexCount"],2)
        vertices=mesh.validation["problemVertexDetails"]
        self.assertTrue(all(v["linkComponentCount"]==1 for v in vertices))
        self.assertTrue(all(4 in v["linkDegrees"].values() for v in vertices))

    def test_connected_detour_is_intra_component_point_contact(self):
        cells=((0,0,0),(-1,0,0),(-2,0,0),(-2,0,1),(-2,0,2),(-1,0,2),(0,0,2),(1,0,2),(1,1,2),(1,1,1));audit=audit_unit_cells(cells,'U');self.assertEqual(audit["componentCount"],1);self.assertEqual(audit["touchEdgeCount"],0);self.assertTrue(any(c["classification"]=="IntraComponentTouchPoint" for c in audit["contacts"]))

    def test_edge_contact_suppresses_duplicate_point_reports(self):
        audit=audit_unit_cells(((0,0,0),(1,1,0)),'U');self.assertEqual(audit["touchEdgeCount"],1);self.assertEqual(audit["touchPointCount"],0)

    def test_filled_cube_has_no_point_contact(self):
        cells=[(x,y,z) for x in (0,1) for y in (0,1) for z in (0,1)];self.assertTrue(audit_unit_cells(cells,'U')["passed"])

    def test_unit_list_missing_material_rejected(self):
        self.assertFalse(run_stage_seven(*self.args,MeshBuildSpec(("INTR","FILL")))["passed"])

    def test_duplicate_unit_rejected(self):
        self.assertFalse(run_stage_seven(*self.args,MeshBuildSpec(("INTR","INTR","FILL","OLD_LOWER")))["passed"])

    def test_unsupported_coordinate_frame_rejected(self):
        bad=MeshBuildSpec(self.spec.unit_ids,"DeformedWorld",True)
        self.assertFalse(run_stage_seven(*self.args,bad)["passed"])

    def test_triangulation_cannot_be_disabled(self):
        bad=MeshBuildSpec(self.spec.unit_ids,"SourceMaterialGrid",False)
        self.assertFalse(run_stage_seven(*self.args,bad)["passed"])

    def test_manifest_authorizes_refinement(self):
        result=run_stage_seven(*self.args,self.spec)
        self.assertEqual(stage_seven_manifest(result)["nextAuthorizedStage"],
                         "adaptive_refinement_and_boolean")


if __name__=="__main__": unittest.main()
