"""Authenticated stochastic realization to representative section."""
from .export.contract_integrity import canonical_json_bytes,sha256_hex
from .geometry.regular_grid import RegularGrid3D
from .stage2 import run_stage_two
from .stage10 import run_stage_ten
from .stratigraphy.stack_spec import StackBuildSpec,StackLayerSpec
from .stratigraphy.stochastic_stack_adapter import build_stack_from_stochastic_thickness

def run_stochastic_to_section(config,result,top,deferred,*specs,tolerance=1e-9):
 grid=RegularGrid3D.from_extent(config.extent);skip=set(deferred)
 ids=[u.unit_id for u in sorted(config.units,key=lambda u:u.order_index) if u.unit_id not in skip]
 try:
  _,report=build_stack_from_stochastic_thickness(grid=grid,top_surface=top,stochastic_result=result,expected_unit_ids=ids,zero_thickness_tolerance=tolerance)
  stack=StackBuildSpec({"values":top},tuple(StackLayerSpec(x["unitId"],{"values":x["thicknessValues"]}) for x in result["layers"]),tuple(deferred),tolerance)
  s2=run_stage_two(config,stack)
  if not s2["passed"]:return {"passed":False,"decision":"Rejected","stage":"stochastic_to_section","errors":[{"code":"BlockedByStageTwo"}],"stageTwo":s2}
  s10=run_stage_ten(config,stack,*specs)
 except Exception as e:return {"passed":False,"decision":"Rejected","stage":"stochastic_to_section","errors":[{"code":"StochasticPipelineFailed","message":str(e)}]}
 out={"passed":bool(s10["passed"]),"decision":"Experimental" if s10["passed"] else "Rejected","stage":"stochastic_to_section","syntheticDisclosure":"Synthetic geological hypothesis / 疑似地質モデル","sourcePayloadSha256":report["sourcePayloadSha256"],"adapterReport":report,"stageTwoPassed":True,"stageTen":s10,"uncertaintyProjection":"RepresentativeBaselineOnly"}
 digest_view={"sourcePayloadSha256":out["sourcePayloadSha256"],"passed":out["passed"],"decision":out["decision"],"polygonCount":s10.get("modelSummary",{}).get("polygonCount"),"unitCount":s10.get("modelSummary",{}).get("unitCount"),"uncertaintyProjection":out["uncertaintyProjection"]}
 out["pipelinePayloadSha256"]=sha256_hex(canonical_json_bytes(digest_view));return out
