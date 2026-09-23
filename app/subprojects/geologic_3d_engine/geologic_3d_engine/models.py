"""Typed domain records for the universal 3D geological engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    DEPOSITION = "Deposition"
    EROSION = "Erosion"
    NONDEPOSITION = "Nondeposition"
    COMPACTION = "Compaction"
    FOLD = "Fold"
    FAULT = "Fault"
    INTRUSION = "Intrusion"
    ARTIFICIAL_MODIFICATION = "ArtificialModification"


class RelationType(str, Enum):
    ABOVE = "Above"
    BELOW = "Below"
    CONTAINS = "Contains"
    BOUNDED_BY = "BoundedBy"
    TRUNCATES = "Truncates"
    DISPLACES = "Displaces"
    INTRUDES = "Intrudes"
    ADJACENT_TO = "AdjacentTo"


@dataclass(frozen=True)
class SourceReference:
    source_id: str
    authority: str
    title: str
    canonical_url: str
    access_date: str
    scope: str

    def validate(self) -> list[dict]:
        errors = []
        for name in ("source_id", "authority", "title", "canonical_url", "access_date", "scope"):
            if not getattr(self, name).strip():
                errors.append({"code": "MissingSourceField", "sourceId": self.source_id,
                               "field": name})
        if self.scope not in {"Global", "Domain", "Environment", "Region", "DatasetSpecific"}:
            errors.append({"code": "InvalidSourceScope", "sourceId": self.source_id,
                           "scope": self.scope})
        return errors


@dataclass(frozen=True)
class CoordinateReference:
    horizontal_crs: str
    vertical_datum: str
    linear_unit: str
    axis_order: str = "XYZ"

    def validate(self) -> list[dict]:
        errors = []
        if not self.horizontal_crs.strip():
            errors.append({"code": "MissingHorizontalCRS"})
        if not self.vertical_datum.strip():
            errors.append({"code": "MissingVerticalDatum"})
        if self.linear_unit not in {"m", "mm", "ft"}:
            errors.append({"code": "UnsupportedLinearUnit", "value": self.linear_unit})
        if self.axis_order != "XYZ":
            errors.append({"code": "UnsupportedAxisOrder", "value": self.axis_order})
        return errors


@dataclass(frozen=True)
class Extent3D:
    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]
    base_cell_size: tuple[float, float, float]

    def validate(self) -> list[dict]:
        errors = []
        if any(high <= low for low, high in zip(self.minimum, self.maximum)):
            errors.append({"code": "InvalidExtent", "minimum": self.minimum,
                           "maximum": self.maximum})
        if any(size <= 0 for size in self.base_cell_size):
            errors.append({"code": "InvalidCellSize", "value": self.base_cell_size})
        return errors


@dataclass(frozen=True)
class GeologicalUnit:
    unit_id: str
    name: str
    order_index: int
    source_ids: tuple[str, ...]
    normalized_lithology: str | None = None
    term_status: str = "Unverified"

    def validate(self) -> list[dict]:
        errors = []
        if not self.unit_id or not self.name:
            errors.append({"code": "MissingUnitIdentity", "unitId": self.unit_id})
        if self.order_index < 0:
            errors.append({"code": "NegativeUnitOrder", "unitId": self.unit_id})
        if not self.source_ids:
            errors.append({"code": "UnitWithoutSource", "unitId": self.unit_id})
        if self.term_status not in {"Current", "Legacy", "LocalRelativeUnit",
                                   "DerivedDisplayLabel", "Unverified", "Deprecated"}:
            errors.append({"code": "InvalidTermStatus", "unitId": self.unit_id})
        return errors


@dataclass(frozen=True)
class GeologicalEvent:
    event_id: str
    event_type: EventType
    order_index: int
    source_ids: tuple[str, ...]
    affected_unit_ids: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[dict]:
        errors = []
        if not self.event_id:
            errors.append({"code": "MissingEventId"})
        if self.order_index < 0:
            errors.append({"code": "NegativeEventOrder", "eventId": self.event_id})
        if not self.source_ids:
            errors.append({"code": "EventWithoutSource", "eventId": self.event_id})
        return errors


@dataclass(frozen=True)
class TopologyRelation:
    relation_id: str
    relation_type: RelationType
    source_id: str
    target_id: str
    evidence_source_ids: tuple[str, ...]
    confidence: float

    def validate(self) -> list[dict]:
        errors = []
        if not self.relation_id or self.source_id == self.target_id:
            errors.append({"code": "InvalidRelationIdentity", "relationId": self.relation_id})
        if not 0.0 <= self.confidence <= 1.0:
            errors.append({"code": "InvalidRelationConfidence", "relationId": self.relation_id})
        if not self.evidence_source_ids:
            errors.append({"code": "RelationWithoutEvidence", "relationId": self.relation_id})
        return errors
