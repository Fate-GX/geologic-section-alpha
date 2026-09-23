"""Pre-B-rep cubical-grid contact audit without changing material labels."""
from collections import deque

def _component_ids(cells):
 remaining=set(cells);ids={};component=0
 while remaining:
  start=remaining.pop();ids[start]=component;queue=deque([start])
  while queue:
   p=queue.popleft()
   for axis in range(3):
    for step in (-1,1):
     q=list(p);q[axis]+=step;q=tuple(q)
     if q in remaining:remaining.remove(q);ids[q]=component;queue.append(q)
  component+=1
 return ids

def audit_unit_cells(cells,unit_id):
 """Find alternating diagonal occupancy around a grid edge."""
 cells=set(tuple(c) for c in cells);component_ids=_component_ids(cells);contacts=[]
 for p in sorted(cells):
  for a,b in ((0,1),(0,2),(1,2)):
   for da in (-1,1):
    for db in (-1,1):
     q=list(p);q[a]+=da;q[b]+=db;q=tuple(q)
     if q not in cells or q<=p:continue
     changed=[a,b]
     r=list(p);r[a]=q[a];s=list(p);s[b]=q[b];r,s=tuple(r),tuple(s)
     if r in cells or s in cells:continue
     ids=sorted({component_ids[p],component_ids[q]})
     contacts.append({"unitId":unit_id,"classification":"IntraComponentTouchEdge" if len(ids)==1 else "InterComponentTouchEdge","sourceVoxels":[list(p),list(q)],"sourceComponentIds":ids,"missingFaceBridgeVoxels":[list(r),list(s)]})
 vertex_cells={}
 for cell in cells:
  for ox in (0,1):
   for oy in (0,1):
    for oz in (0,1):vertex_cells.setdefault((cell[0]+ox,cell[1]+oy,cell[2]+oz),set()).add(cell)
 point_contacts=[]
 for vertex,incident in sorted(vertex_cells.items()):
  if len(incident)<2:continue
  remaining=set(incident);local=[]
  while remaining:
   group={remaining.pop()};queue=deque(group)
   while queue:
    p=queue.popleft()
    for axis in range(3):
     for step in (-1,1):
      q=list(p);q[axis]+=step;q=tuple(q)
      if q in remaining:remaining.remove(q);group.add(q);queue.append(q)
   local.append(group)
  if len(local)<2:continue
  cross_edge=False
  for i in range(len(local)):
   for j in range(i+1,len(local)):
    if any(sum(a!=b for a,b in zip(p,q))==2 for p in local[i] for q in local[j]):cross_edge=True
  if cross_edge:continue
  ids=sorted({component_ids[c] for c in incident})
  point_contacts.append({"unitId":unit_id,"classification":"IntraComponentTouchPoint" if len(ids)==1 else "InterComponentTouchPoint","vertexCoordinate":list(vertex),"sourceVoxels":[list(c) for c in sorted(incident)],"sourceComponentIds":ids,"localFaceComponentCount":len(local)})
 all_contacts=contacts+point_contacts
 return {"unitId":unit_id,"componentCount":len(set(component_ids.values())),"touchEdgeCount":len(contacts),"touchPointCount":len(point_contacts),"contacts":all_contacts,"passed":not all_contacts,"representation":"PreBrepCubicalContactAudit"}

def audit_label_grid(labels_zyx,unit_ids):
 audits=[]
 for unit in unit_ids:
  cells={(x,y,z) for z,layer in enumerate(labels_zyx) for y,row in enumerate(layer) for x,value in enumerate(row) if value==unit}
  audits.append(audit_unit_cells(cells,unit))
 return {"passed":all(x["passed"] for x in audits),"gate":"PreBrepVoxelTopologyAudit","unitAudits":audits,"touchEdgeCount":sum(x["touchEdgeCount"] for x in audits),"touchPointCount":sum(x["touchPointCount"] for x in audits)}
