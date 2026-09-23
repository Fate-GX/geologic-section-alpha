"""Build a neutral contract consumed by a standard AutoCAD .NET writer."""

from __future__ import annotations

import hashlib
import json
import math

from .contract_integrity import canonical_json_bytes


def build_autocad_contract(section,spec,engine_version,uncertainty_section=None):
    spec.validate(section); drafting={u.unit_id:u for u in spec.units}; polygons=[]
    for unit in section["unitSections"]:
        style=drafting[unit["unitId"]]
        for polygon in unit["polygons"]:
            vertices=polygon["verticesUV"]
            if not all(len(point)==2 and all(math.isfinite(float(value)) for value in point)
                       for point in vertices):
                raise ValueError("polygon vertices must contain only finite UV coordinates")
            if len(vertices)<4 or vertices[0]!=vertices[-1] or polygon["area"]<=0:
                raise ValueError("only closed positive-area polygons can be exported")
            polygons.append({"polygonId":polygon["polygonId"],"unitId":unit["unitId"],
              "displayName":style.display_name,"boundaryLayer":spec.boundary_layer,
              "hatchLayer":style.layer_name,"trueColorRGB":list(style.rgb),
              "vertices":[list(map(float,p)) for p in vertices[:-1]],"closed":True,
              "hatchPattern":"SOLID","associative":True,
              "sourceCoordinateFrame":polygon["sourceCoordinateFrame"]})
    ids=[p["polygonId"] for p in polygons]
    if len(set(ids))!=len(ids): raise ValueError("polygon IDs must be unique")
    body={"contractVersion":"1.0","drawingId":spec.drawing_id,
      "artifactType":"SyntheticGeologicCrossSection","notForDesign":True,
      "syntheticDisclosure":spec.synthetic_disclosure,"generatorVersion":engine_version,
      "dwgVersion":spec.dwg_version,"sectionId":section["sectionId"],
      "coordinateFrame":"SectionUV","sourceCoordinateFrame":section["validation"]["coordinateFrame"],
      "nativeApiPlan":["Polyline.AddVertexAt","Hatch.AppendLoop","Hatch.EvaluateHatch",
        "Color.FromRgb","DrawOrderTable.MoveToBottom","Database.SaveAs"],
      "polygons":polygons}
    if uncertainty_section is not None:
        if not uncertainty_section.get("validation",{}).get("passed"):
            raise ValueError("uncertainty section must pass before Stage-11 integration")
        body["uncertaintyVisualization"]={
          "artifactRole":"DiagnosticOverlay_NotLithologyGeometry",
          "representation":uncertainty_section["representation"],
          "sectionId":uncertainty_section["sectionId"],
          "samplingMethod":uncertainty_section["samplingMethod"],
          "samplingSpacingPolicy":uncertainty_section["samplingSpacingPolicy"],
          "samplingSpacing":uncertainty_section["samplingSpacing"],
          "coverageStatus":uncertainty_section["coverageStatus"],
          "uValues":uncertainty_section["uValues"],"vValues":uncertainty_section["vValues"],
          "materialProbabilityVU":uncertainty_section["materialProbabilityVU"],
          "normalizedEntropyVU":uncertainty_section["normalizedEntropyVU"],
          "disagreementMaskVU":uncertainty_section["disagreementMaskVU"],
          "inDomainMaskVU":uncertainty_section["inDomainMaskVU"],
          "cadEntityAuthorization":"None_DiagnosticDataOnly",
          "mustNotCreateLithologyBoundaries":True,"mustNotCreateLithologyHatches":True,
          "visualizationPolicy":{"entropy":"ContinuousDiagnosticPalette",
            "disagreement":"DiagnosticMask","outOfDomain":"TransparentNoData",
            "legendRequired":True,"syntheticUncertaintyDisclosureRequired":True}}
    canonical=canonical_json_bytes(body)
    body["contractSha256"]=hashlib.sha256(canonical).hexdigest()
    body["validation"]={"passed":bool(polygons),"polygonCount":len(polygons),
      "allClosed":all(p["closed"] for p in polygons),"allSolid":all(p["hatchPattern"]=="SOLID" for p in polygons),
      "allAssociative":all(p["associative"] for p in polygons),"uniquePolygonIds":len(ids)==len(set(ids)),
      "uncertaintyVisualizationPresent":uncertainty_section is not None,
      "uncertaintySeparatedFromLithologyGeometry":uncertainty_section is None or
        body["uncertaintyVisualization"]["cadEntityAuthorization"]=="None_DiagnosticDataOnly"}
    return body
