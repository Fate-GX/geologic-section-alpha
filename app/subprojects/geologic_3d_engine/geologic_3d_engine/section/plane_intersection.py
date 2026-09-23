"""Triangle-plane intersection followed by topology-preserving loop assembly."""

from __future__ import annotations

from collections import defaultdict
import math


def extract_section(brep_model, spec):
    spec.validate(); u_axis, v_axis, normal = spec.basis()
    unit_sections=[]; errors=[]
    for mesh in brep_model.unit_meshes:
        segments=[]; coplanar=0
        for triangle in mesh.triangles:
            points=[mesh.vertices[i] for i in triangle]
            segment,state=_triangle_plane(points,spec.origin,normal,spec.tolerance)
            if state=="Coplanar": coplanar+=1
            elif segment is not None:
                projected=[_project(p,spec.origin,u_axis,v_axis) for p in segment]
                if _inside(projected,spec): segments.append(projected)
        loops,loop_errors=_assemble_loops(segments,spec.tolerance)
        errors.extend({"unitId":mesh.unit_id,**item} for item in loop_errors)
        polygons=[]
        for index,loop in enumerate(loops):
            area=_signed_area(loop)
            polygons.append({"polygonId":f"{spec.section_id}_{mesh.unit_id}_{index}",
                "unitId":mesh.unit_id,"verticesUV":[list(p) for p in loop],
                "signedArea":area,"area":abs(area),"closed":loop[0]==loop[-1],
                "sourceCoordinateFrame":brep_model.coordinate_frame})
        unit_sections.append({"unitId":mesh.unit_id,"segmentCount":len(segments),
            "coplanarTriangleCount":coplanar,"polygons":polygons,
            "polygonCount":len(polygons),"sectionArea":sum(p["area"] for p in polygons)})
        if coplanar:
            errors.append({"code":"CoplanarTriangleAmbiguity","unitId":mesh.unit_id,
                           "triangleCount":coplanar})
    polygon_count=sum(x["polygonCount"] for x in unit_sections)
    validation={"passed":not errors and polygon_count>0,"gate":"ExactBrepPlaneIntersection",
        "errors":errors,"unitCount":len(unit_sections),"polygonCount":polygon_count,
        "allLoopsClosed":not errors and polygon_count>0,"coordinateFrame":brep_model.coordinate_frame,
        "intersectionMethod":"ExactLinearTrianglePlaneIntersection",
        "clippingPolicy":"RejectSegmentsOutsideDeclaredRectangle"}
    return {"sectionId":spec.section_id,"origin":list(spec.origin),"normal":list(normal),
        "uDirection":list(u_axis),"vDirection":list(v_axis),"uRange":list(spec.u_range),
        "vRange":list(spec.v_range),"unitSections":unit_sections,"validation":validation,
        "representation":"ClosedSectionPolygonsUV"}


def _triangle_plane(points,origin,normal,tol):
    distances=[sum((p[i]-origin[i])*normal[i] for i in range(3)) for p in points]
    if all(abs(d)<=tol for d in distances): return None,"Coplanar"
    hits=[]
    for i,j in ((0,1),(1,2),(2,0)):
        a,b,da,db=points[i],points[j],distances[i],distances[j]
        if abs(da)<=tol: hits.append(tuple(a))
        if da*db < -tol*tol:
            t=da/(da-db); hits.append(tuple(a[k]+t*(b[k]-a[k]) for k in range(3)))
    hits=_unique(hits,tol)
    if len(hits)==2 and _distance(hits[0],hits[1])>tol: return hits,"Segment"
    return None,"None"


def _assemble_loops(segments,tol):
    points={}; edges=set()
    def key(p): return tuple(round(v/tol) for v in p)
    for a,b in segments:
        ka,kb=key(a),key(b); points.setdefault(ka,a); points.setdefault(kb,b)
        if ka!=kb: edges.add(tuple(sorted((ka,kb))))
    adjacency=defaultdict(set)
    for a,b in edges: adjacency[a].add(b); adjacency[b].add(a)
    errors=[]
    for vertex,neighbors in adjacency.items():
        if len(neighbors)!=2: errors.append({"code":"OpenOrBranchedSectionGraph",
            "vertex":list(points[vertex]),"degree":len(neighbors)})
    if errors: return [],errors
    loops=[]; remaining=set(edges)
    while remaining:
        start,cur=next(iter(remaining)); previous=start
        remaining.discard(tuple(sorted((start,cur))))
        loop=[points[start],points[cur]]
        while cur!=start:
            candidates=[n for n in adjacency[cur] if n!=previous]
            nxt=candidates[0]
            remaining.discard(tuple(sorted((cur,nxt))))
            previous,cur=cur,nxt; loop.append(points[cur])
            if len(loop)>len(edges)+2:
                return [],[{"code":"LoopAssemblyOverflow"}]
        loops.append(_remove_collinear(loop,tol))
    return loops,[]


def _remove_collinear(loop,tol):
    body=loop[:-1]; output=[]
    for i,p in enumerate(body):
        a=body[i-1]; b=body[(i+1)%len(body)]
        cross=(p[0]-a[0])*(b[1]-p[1])-(p[1]-a[1])*(b[0]-p[0])
        if abs(cross)>tol: output.append(p)
    return output+[output[0]] if output else loop


def _project(point,origin,u,v):
    delta=tuple(point[i]-origin[i] for i in range(3))
    return (sum(delta[i]*u[i] for i in range(3)),sum(delta[i]*v[i] for i in range(3)))
def _inside(segment,spec):
    return all(spec.u_range[0]-spec.tolerance<=p[0]<=spec.u_range[1]+spec.tolerance and
               spec.v_range[0]-spec.tolerance<=p[1]<=spec.v_range[1]+spec.tolerance for p in segment)
def _unique(points,tol):
    out=[]
    for p in points:
        if not any(_distance(p,q)<=tol for q in out): out.append(p)
    return out
def _distance(a,b): return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
def _signed_area(loop): return .5*sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(loop,loop[1:]))
