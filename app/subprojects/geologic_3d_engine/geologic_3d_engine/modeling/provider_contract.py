"""Versioned extension contract for future high-accuracy geology providers."""
from typing import Protocol,Sequence,Mapping
from .lithology_section_model import verify_lithology_section_model

class LithologySectionProvider(Protocol):
    provider_id: str
    contract_version: str
    def generate(self,stations_m:Sequence[float],request:Mapping)->dict: ...

SUPPORTED_LITHOLOGY_CONTRACT="LithologySectionModel-1.0"

def provider_manifest(provider):
    provider_id=getattr(provider,"provider_id",None);version=getattr(provider,"contract_version",None)
    if not isinstance(provider_id,str) or not provider_id or version!=SUPPORTED_LITHOLOGY_CONTRACT:
        raise ValueError("provider must declare a supported stable contract")
    return {"providerId":provider_id,"contractVersion":version,
      "replaceableWithoutTerrainOrGuiChanges":True}

def invoke_lithology_provider(provider,stations_m,request):
    """Invoke a provider through the stable boundary and verify its artifact."""
    provider_manifest(provider)
    if not isinstance(request,Mapping):raise ValueError("provider request must be a mapping")
    forbidden={"terrain","terrainElevationM","dem","surfaceElevationM"}.intersection(request)
    if forbidden:raise ValueError("terrain data is forbidden in a lithology-provider request")
    result=provider.generate(stations_m,request)
    verify_lithology_section_model(result)
    if result.get("providerId")!=provider.provider_id:raise ValueError("provider artifact identity mismatch")
    return result
