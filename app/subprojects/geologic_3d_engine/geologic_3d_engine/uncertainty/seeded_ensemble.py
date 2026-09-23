"""Deterministic evidence-bounded Stage-9 ensemble execution."""

from __future__ import annotations

from collections import Counter
import math
import random

from ..events.intrusion_spec import IntrusionSpec
from ..stage8 import run_stage_eight

def _failed_gate_diagnostics(result):
    """Preserve nested gate failures without changing pass/fail semantics."""
    found=[]
    def visit(value,path):
        if isinstance(value,dict):
            if value.get("passed") is False and (value.get("errors") or value.get("gate")):
                found.append({"path":path,"gate":value.get("gate"),
                    "errors":value.get("errors",[]),
                    "details":{k:v for k,v in value.items() if k not in {"passed","gate","errors"}}})
            for key,item in value.items():
                if key not in {"adaptiveModel","stageOne"}:visit(item,f"{path}.{key}")
        elif isinstance(value,list):
            for index,item in enumerate(value):visit(item,f"{path}[{index}]")
    visit(result,"stageEight")
    return found


def build_seeded_ensemble(config, stack_spec, event_spec, compaction_spec,
                          structural_spec, intrusion_spec, mesh_spec,
                          refinement_spec, ensemble_spec):
    ensemble_spec.validate(config, intrusion_spec)
    members = []
    valid_models = []
    for index in range(ensemble_spec.member_count):
        seed = config.random_seed + ensemble_spec.seed_offset + index
        sampled, values = _sample_intrusion_spec(intrusion_spec, ensemble_spec, seed)
        result = run_stage_eight(config, stack_spec, event_spec, compaction_spec,
                                 structural_spec, sampled, mesh_spec, refinement_spec)
        member = {"memberIndex": index, "seed": seed, "parameters": values,
                  "passed": result["passed"], "decision": result["decision"],
                  "errors": result.get("errors", []),
                  "failedGateDiagnostics": _failed_gate_diagnostics(result)}
        if result["passed"]:
            model = result["adaptiveModel"]
            member["topologySignature"] = model.validation["refinedTopologySignature"]
            member["unitVolumes"] = model.validation["refinedUnitVolumes"]
            valid_models.append(model)
        members.append(member)
    valid_fraction = len(valid_models) / ensemble_spec.member_count
    errors = []
    if valid_fraction < ensemble_spec.minimum_valid_fraction:
        errors.append({"code": "ValidMemberFractionBelowMinimum",
                       "validFraction": valid_fraction})
    probability, entropy, disagreement, mean_entropy = _disagreement(valid_models)
    if mean_entropy > ensemble_spec.maximum_mean_normalized_entropy:
        errors.append({"code": "MeanEntropyAboveMaximum", "value": mean_entropy})
    validation = {"passed": not errors, "gate": "SeededUncertaintyEnsemble",
        "errors": errors, "memberCount": ensemble_spec.member_count,
        "validMemberCount": len(valid_models), "validMemberFraction": valid_fraction,
        "minimumValidFraction": ensemble_spec.minimum_valid_fraction,
        "meanNormalizedEntropy": mean_entropy,
        "maximumMeanNormalizedEntropy": ensemble_spec.maximum_mean_normalized_entropy,
        "disagreementCellCount": sum(1 for layer in disagreement for row in layer for v in row if v),
        "deterministicSeedFormula": "config.randomSeed + seedOffset + memberIndex"}
    return {"members": members, "materialProbabilityZYX": probability,
            "normalizedEntropyZYX": entropy, "disagreementMaskZYX": disagreement,
            "validation": validation,
            "representation": "SeededEvidenceBoundedMaterialProbabilityEnsemble"}


def _sample_intrusion_spec(base, spec, seed):
    rng = random.Random(seed)
    operations = [dict(item) for item in base.operations]
    sampled = []
    for item in spec.parameter_ranges:
        value = rng.uniform(item.minimum, item.maximum)
        operation = next(op for op in operations if str(op.get("eventId")) == item.event_id)
        operation[item.parameter] = value
        sampled.append({"eventId": item.event_id, "parameter": item.parameter,
                        "value": value, "minimum": item.minimum, "maximum": item.maximum,
                        "distribution": item.distribution,
                        "evidenceSourceIds": list(item.evidence_source_ids)})
    return IntrusionSpec(tuple(operations)), sampled


def _disagreement(models):
    if not models:
        return [], [], [], 0.0
    labels = [model.fine_labels_zyx for model in models]
    nz, ny, nx = len(labels[0]), len(labels[0][0]), len(labels[0][0][0])
    probability, entropy, disagreement = [], [], []
    entropy_sum = 0.0
    for z in range(nz):
        p_layer, e_layer, d_layer = [], [], []
        for y in range(ny):
            p_row, e_row, d_row = [], [], []
            for x in range(nx):
                counts = Counter(member[z][y][x] for member in labels)
                probs = {str(k): v / len(labels) for k, v in sorted(counts.items(), key=lambda p:str(p[0]))}
                raw = -sum(p * math.log(p) for p in probs.values())
                normalized = raw / math.log(len(labels)) if len(labels) > 1 else 0.0
                p_row.append(probs); e_row.append(normalized); d_row.append(len(counts) > 1)
                entropy_sum += normalized
            p_layer.append(p_row); e_layer.append(e_row); d_layer.append(d_row)
        probability.append(p_layer); entropy.append(e_layer); disagreement.append(d_layer)
    return probability, entropy, disagreement, entropy_sum / (nx * ny * nz)
