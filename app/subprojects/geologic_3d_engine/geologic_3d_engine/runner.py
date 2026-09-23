"""Stage-one engine orchestration and immutable run-manifest creation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from . import __version__
from .config import EngineConfig
from .topology import GeologicalTopologyGraph


def configuration_fingerprint(config: EngineConfig) -> str:
    payload = json.dumps(config.to_dict(), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_stage_one(config: EngineConfig) -> dict:
    schema = config.validate_schema()
    topology = GeologicalTopologyGraph(config).validate() if schema["passed"] else {
        "passed": False, "errors": [{"code": "BlockedBySchemaGate"}],
        "gate": "TopologyAndChronology", "nodeCount": 0, "relationCount": 0,
        "topologySignature": []}
    passed = schema["passed"] and topology["passed"]
    return {"passed": passed, "decision": "Experimental" if passed else "Rejected",
            "stage": "schemas_and_topology_graph", "gates": [schema, topology]}


def create_run_manifest(config: EngineConfig, validation: dict,
                        created_at: datetime | None = None) -> dict:
    timestamp = (created_at or datetime.now(timezone.utc)).isoformat()
    return {"engineVersion": __version__, "createdAt": timestamp,
            "projectName": config.project_name, "regionalProfileId": config.regional_profile_id,
            "syntheticDisclosure": config.synthetic_disclosure,
            "randomSeed": config.random_seed,
            "configurationSha256": configuration_fingerprint(config),
            "coordinateReference": config.to_dict()["coordinateReference"],
            "extent": config.to_dict()["extent"], "validation": validation,
            "decision": validation["decision"], "geometryGenerated": False,
            "nextAuthorizedStage": "positive_thickness_3d_stack" if validation["passed"] else None}
