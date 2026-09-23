"""Default low-complexity provider behind the common lithology contract."""
from .lithology_section_model import generate_basic_relative_depth_lithology

class BasicCorrelatedLithologyProvider:
    provider_id="BasicCorrelatedRelativeDepth-1.0"
    contract_version="LithologySectionModel-1.0"
    capability_level="BasicReasonableSyntheticSection"

    def generate(self,stations_m,request):
        allowed={"layers","seed","rangeM","logStd"}
        unknown=set(request)-allowed
        if unknown:raise ValueError(f"unsupported basic-provider keys: {sorted(unknown)}")
        return generate_basic_relative_depth_lithology(stations_m,request["layers"],seed=request["seed"],
          range_m=request.get("rangeM",500),log_std=request.get("logStd",.18))
