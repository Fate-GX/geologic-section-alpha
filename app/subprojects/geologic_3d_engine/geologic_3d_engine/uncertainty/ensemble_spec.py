"""Stage-9 evidence-bounded ensemble input contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParameterRange:
    event_id: str
    parameter: str
    minimum: float
    maximum: float
    distribution: str
    evidence_source_ids: tuple[str, ...]


@dataclass(frozen=True)
class EnsembleSpec:
    member_count: int
    seed_offset: int
    parameter_ranges: tuple[ParameterRange, ...]
    minimum_valid_fraction: float = 1.0
    maximum_mean_normalized_entropy: float = 1.0

    @classmethod
    def from_dict(cls, data):
        ranges = tuple(ParameterRange(str(item.get("eventId", "")),
            str(item.get("parameter", "")), float(item.get("minimum", 0)),
            float(item.get("maximum", 0)), str(item.get("distribution", "Uniform")),
            tuple(item.get("evidenceSourceIds", [])))
            for item in data.get("intrusionParameterRanges", []))
        return cls(int(data.get("memberCount", 0)), int(data.get("seedOffset", 0)), ranges,
                   float(data.get("minimumValidFraction", 1.0)),
                   float(data.get("maximumMeanNormalizedEntropy", 1.0)))

    def validate(self, config, intrusion_spec):
        if self.member_count < 2:
            raise ValueError("memberCount must be at least 2")
        if not 0 < self.minimum_valid_fraction <= 1:
            raise ValueError("minimumValidFraction must be in (0,1]")
        if not 0 <= self.maximum_mean_normalized_entropy <= 1:
            raise ValueError("maximumMeanNormalizedEntropy must be in [0,1]")
        source_ids = {source.source_id for source in config.sources}
        operations = {str(item.get("eventId", "")): item for item in intrusion_spec.operations}
        seen = set()
        for item in self.parameter_ranges:
            operation = operations.get(item.event_id)
            if operation is None:
                raise ValueError(f"unknown intrusion eventId: {item.event_id}")
            if item.parameter not in {"planeOffset", "halfThickness"}:
                raise ValueError("Stage 9 supports planeOffset and halfThickness ranges")
            if item.parameter not in operation:
                raise ValueError(f"parameter is absent from intrusion operation: {item.parameter}")
            if item.minimum > item.maximum:
                raise ValueError("parameter minimum must not exceed maximum")
            if item.parameter == "halfThickness" and item.minimum <= 0:
                raise ValueError("halfThickness range must remain positive")
            if item.distribution != "Uniform":
                raise ValueError("only explicitly bounded Uniform sampling is supported")
            if not item.evidence_source_ids or not set(item.evidence_source_ids) <= source_ids:
                raise ValueError("each parameter range requires valid evidenceSourceIds")
            key = (item.event_id, item.parameter)
            if key in seen:
                raise ValueError("duplicate uncertainty parameter target")
            seen.add(key)
        if not self.parameter_ranges:
            raise ValueError("at least one evidence-bounded parameter range is required")
        return self


def load_ensemble_spec(path: str | Path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("ensemble specification root must be an object")
    return EnsembleSpec.from_dict(data)
