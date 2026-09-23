"""Closed, oriented boundary representations extracted from labeled voxels."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class UnitBoundaryMesh:
    unit_id: str
    vertices: tuple[tuple[float, float, float], ...]
    quads: tuple[tuple[int, int, int, int], ...]
    triangles: tuple[tuple[int, int, int], ...]
    voxel_count: int
    connected_component_count: int
    validation: dict

    def to_dict(self):
        return {"unitId": self.unit_id, "vertices": [list(v) for v in self.vertices],
                "quads": [list(f) for f in self.quads],
                "triangles": [list(f) for f in self.triangles],
                "voxelCount": self.voxel_count,
                "connectedComponentCount": self.connected_component_count,
                "validation": self.validation}


@dataclass(frozen=True)
class ClosedBrepModel:
    coordinate_frame: str
    unit_meshes: tuple[UnitBoundaryMesh, ...]
    validation: dict

    def to_dict(self):
        return {"coordinateFrame": self.coordinate_frame,
                "unitMeshes": [mesh.to_dict() for mesh in self.unit_meshes],
                "validation": self.validation,
                "representation": "ClosedOrientedVoxelBoundaryBrep"}


_FACES = (
    ((-1, 0, 0), ((0,0,0),(0,0,1),(0,1,1),(0,1,0))),
    (( 1, 0, 0), ((1,0,0),(1,1,0),(1,1,1),(1,0,1))),
    ((0, -1, 0), ((0,0,0),(1,0,0),(1,0,1),(0,0,1))),
    ((0,  1, 0), ((0,1,0),(0,1,1),(1,1,1),(1,1,0))),
    ((0, 0, -1), ((0,0,0),(0,1,0),(1,1,0),(1,0,0))),
    ((0, 0,  1), ((0,0,1),(1,0,1),(1,1,1),(0,1,1))),
)


def build_closed_breps(labels_zyx, grid, unit_ids) -> ClosedBrepModel:
    meshes = tuple(_build_unit(labels_zyx, grid, unit_id) for unit_id in unit_ids)
    errors = []
    for mesh in meshes:
        errors.extend({"unitId": mesh.unit_id, **error}
                      for error in mesh.validation["errors"])
    validation = {"passed": not errors, "gate": "ClosedOrientedManifoldBrep",
                  "errors": errors, "unitCount": len(meshes),
                  "allUnitsClosed": all(mesh.validation["closed"] for mesh in meshes),
                  "allUnitsOriented": all(mesh.validation["oriented"] for mesh in meshes),
                  "unitDiagnostics": [{"unitId": mesh.unit_id,
                    "voxelCount": mesh.voxel_count,
                    "connectedComponentCount": mesh.connected_component_count,
                    "vertexCount": len(mesh.vertices), "quadCount": len(mesh.quads),
                    "triangleCount": len(mesh.triangles),
                    "validation": mesh.validation} for mesh in meshes],
                  "coordinateFrame": "SourceMaterialGrid"}
    return ClosedBrepModel("SourceMaterialGrid", meshes, validation)


def _build_unit(labels, grid, unit_id):
    cells = {(x,y,z) for z in range(grid.nz) for y in range(grid.ny)
             for x in range(grid.nx) if labels[z][y][x] == unit_id}
    return _build_cells(grid, unit_id, cells)


def _build_cells(grid, unit_id, cells):
    vertex_ids, vertices, quads, face_cells, face_normals = {}, [], [], [], []
    for x, y, z in sorted(cells, key=lambda p: (p[2], p[1], p[0])):
        for (dx,dy,dz), corners in _FACES:
            if (x+dx, y+dy, z+dz) in cells:
                continue
            face = []
            for ox,oy,oz in corners:
                key = (x+ox, y+oy, z+oz)
                if key not in vertex_ids:
                    vertex_ids[key] = len(vertices)
                    vertices.append((grid.minimum[0] + key[0]*grid.cell_size[0],
                                     grid.minimum[1] + key[1]*grid.cell_size[1],
                                     grid.minimum[2] + key[2]*grid.cell_size[2]))
                face.append(vertex_ids[key])
            quads.append(tuple(face))
            face_cells.append((x,y,z))
            face_normals.append((dx,dy,dz))
    triangles = tuple((a,b,c) for a,b,c,d in quads) + tuple((a,c,d) for a,b,c,d in quads)
    validation = _validate_mesh(vertices, quads, triangles, len(cells), grid.cell_volume,
                                face_cells,face_normals,cells)
    return UnitBoundaryMesh(unit_id, tuple(vertices), tuple(quads), triangles, len(cells),
                            _component_count(cells), validation)


def analyze_unit_components(labels_zyx, grid, unit_id):
    """Build each 6-connected component independently without repairing labels."""
    cells={(x,y,z) for z in range(grid.nz) for y in range(grid.ny)
           for x in range(grid.nx) if labels_zyx[z][y][x]==unit_id}
    remaining=set(cells);groups=[]
    while remaining:
        group={remaining.pop()};queue=deque(group)
        while queue:
            x,y,z=queue.popleft()
            for d in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                neighbor=(x+d[0],y+d[1],z+d[2])
                if neighbor in remaining:remaining.remove(neighbor);group.add(neighbor);queue.append(neighbor)
        groups.append(group)
    meshes=[_build_cells(grid,f"{unit_id}#component-{i}",g) for i,g in enumerate(groups)]
    relations=[]
    for i in range(len(meshes)):
        for j in range(i+1,len(meshes)):
            shared=set(meshes[i].vertices)&set(meshes[j].vertices)
            relation="Disjoint" if not shared else "TouchPoint" if len(shared)==1 else "TouchEdge" if len(shared)==2 else "TouchFaceOrHigher"
            relations.append({"componentA":i,"componentB":j,"relation":relation,
                              "sharedVertexCount":len(shared),
                              "sharedVertices":[list(v) for v in sorted(shared)]})
    return {"unitId":unit_id,"componentCount":len(meshes),
            "allComponentsManifold":all(m.validation["passed"] for m in meshes),
            "components":[{"componentIndex":i,"voxelCount":m.voxel_count,
              "validation":m.validation} for i,m in enumerate(meshes)],
            "relations":relations,"representation":"ComponentWiseClosedShellDiagnostic"}


def _validate_mesh(vertices, quads, triangles, voxel_count, cell_volume, face_cells,
                   face_normals, cells):
    errors = []
    edge_counts = Counter()
    directed = Counter()
    for face in quads:
        for index in range(4):
            a,b = face[index], face[(index+1)%4]
            edge_counts[tuple(sorted((a,b)))] += 1; directed[(a,b)] += 1
    edge_faces={edge:[] for edge,count in edge_counts.items() if count != 2}
    for face_id,face in enumerate(quads):
        for index in range(4):
            edge=tuple(sorted((face[index],face[(index+1)%4])))
            if edge in edge_faces:edge_faces[edge].append(face_id)
    component_ids=_component_ids(cells);edge_details=[]
    for edge,face_ids in sorted(edge_faces.items()):
        source_cells=[face_cells[i] for i in face_ids];component_set=sorted({component_ids[c] for c in source_cells})
        local=sorted({c for c in cells if any(max(abs(c[k]-s[k]) for k in range(3))<=1 for s in source_cells)})
        edge_details.append({"vertexIds":list(edge),
          "vertexCoordinates":[list(vertices[i]) for i in edge],
          "useCount":edge_counts[edge],"faceIds":face_ids,
          "sourceVoxels":[list(c) for c in source_cells],
          "sourceFaceNormals":[list(face_normals[i]) for i in face_ids],
          "sourceComponentIds":component_set,
          "contactScope":"IntraComponentSelfTouch" if len(component_set)==1 else "InterComponentContact",
          "localOccupiedVoxels":[list(c) for c in local]})
    open_edges=[x for x in edge_details if x["useCount"]<2]
    nonmanifold_edges=[x for x in edge_details if x["useCount"]>2]
    if open_edges:errors.append({"code":"OpenBoundaryEdge","count":len(open_edges),"edges":open_edges})
    if nonmanifold_edges:errors.append({"code":"NonManifoldEdge","count":len(nonmanifold_edges),"edges":nonmanifold_edges})
    orientation_errors = sum(1 for a,b in directed if directed[(a,b)] != directed.get((b,a),0))
    if orientation_errors:
        errors.append({"code":"InconsistentFaceOrientation","count":orientation_errors})
    vertex_faces={i:[] for i in range(len(vertices))}
    for face_id,face in enumerate(quads):
        for vertex in face:vertex_faces[vertex].append(face_id)
    bad_vertices=[]
    for vertex,face_ids in vertex_faces.items():
        link={}
        for face_id in face_ids:
            face=quads[face_id];index=face.index(vertex);a=face[(index-1)%4];b=face[(index+1)%4]
            link.setdefault(a,set()).add(b);link.setdefault(b,set()).add(a)
        remaining=set(link);components=0
        while remaining:
            components+=1;queue=[remaining.pop()]
            while queue:
                node=queue.pop()
                for neighbor in link[node]:
                    if neighbor in remaining:remaining.remove(neighbor);queue.append(neighbor)
        degrees={str(node):len(neighbors) for node,neighbors in sorted(link.items())}
        if components!=1 or any(degree!=2 for degree in degrees.values()):
            bad_vertices.append({"vertexId":vertex,"vertexCoordinate":list(vertices[vertex]),
              "incidentFaceIds":face_ids,"sourceVoxels":[list(face_cells[i]) for i in face_ids],
              "linkComponentCount":components,"linkDegrees":degrees})
    if bad_vertices:errors.append({"code":"NonManifoldVertex","count":len(bad_vertices),"vertices":bad_vertices})
    degenerate = 0
    for a,b,c in triangles:
        p,q,r = vertices[a],vertices[b],vertices[c]
        cross = ((q[1]-p[1])*(r[2]-p[2])-(q[2]-p[2])*(r[1]-p[1]),
                 (q[2]-p[2])*(r[0]-p[0])-(q[0]-p[0])*(r[2]-p[2]),
                 (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0]))
        if math.sqrt(sum(v*v for v in cross)) <= 0:
            degenerate += 1
    if degenerate:
        errors.append({"code":"DegenerateTriangle","count":degenerate})
    mesh_volume = _signed_volume(vertices, triangles)
    expected = voxel_count * cell_volume
    if not math.isclose(mesh_volume, expected, rel_tol=1e-9, abs_tol=1e-9*max(1,expected)):
        errors.append({"code":"MeshVolumeMismatch","meshVolume":mesh_volume,
                       "voxelVolume":expected})
    return {"passed":not errors,"errors":errors,"closed":not open_edges,
            "oriented":not orientation_errors,"manifold":not nonmanifold_edges and not bad_vertices,
            "degenerateTriangleCount":degenerate,"boundaryEdgeCount":len(edge_details),
            "openEdgeCount":len(open_edges),"nonManifoldEdgeCount":len(nonmanifold_edges),
            "nonManifoldVertexCount":len(bad_vertices),"problemVertexDetails":bad_vertices,
            "problemEdgeDetails":edge_details,
            "signedVolume":mesh_volume,"voxelVolume":expected,
            "volumeDifference":mesh_volume-expected}


def _signed_volume(vertices, triangles):
    volume = 0.0
    for a,b,c in triangles:
        p,q,r = vertices[a],vertices[b],vertices[c]
        volume += (p[0]*(q[1]*r[2]-q[2]*r[1]) -
                   p[1]*(q[0]*r[2]-q[2]*r[0]) +
                   p[2]*(q[0]*r[1]-q[1]*r[0])) / 6.0
    return volume


def _component_count(cells):
    remaining=set(cells); count=0
    while remaining:
        count+=1; queue=deque([remaining.pop()])
        while queue:
            x,y,z=queue.popleft()
            for d in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                neighbor=(x+d[0],y+d[1],z+d[2])
                if neighbor in remaining:
                    remaining.remove(neighbor); queue.append(neighbor)
    return count

def _component_ids(cells):
    remaining=set(cells);result={};component=0
    while remaining:
        start=remaining.pop();result[start]=component;queue=deque([start])
        while queue:
            x,y,z=queue.popleft()
            for d in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                n=(x+d[0],y+d[1],z+d[2])
                if n in remaining:remaining.remove(n);result[n]=component;queue.append(n)
        component+=1
    return result
