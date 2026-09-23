"""Configuration parsing shared by GUI, CLI and programmatic execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import (CoordinateReference, EventType, Extent3D, GeologicalEvent,
                     GeologicalUnit, RelationType, SourceReference, TopologyRelation)


def _triple(value, name: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{name} must contain exactly three numbers")
    return tuple(float(item) for item in value)


@dataclass(frozen=True)
class EngineConfig:
    project_name: str
    synthetic_disclosure: str
    random_seed: int
    regional_profile_id: str
    coordinate_reference: CoordinateReference
    extent: Extent3D
    sources: tuple[SourceReference, ...]
    units: tuple[GeologicalUnit, ...]
    events: tuple[GeologicalEvent, ...]
    relations: tuple[TopologyRelation, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EngineConfig":
        coordinate = data.get("coordinateReference", {})
        extent = data.get("extent", {})
        return cls(
            project_name=str(data.get("projectName", "")),
            synthetic_disclosure=str(data.get("syntheticDisclosure", "")),
            random_seed=int(data.get("randomSeed", 0)),
            regional_profile_id=str(data.get("regionalProfileId", "")),
            coordinate_reference=CoordinateReference(
                str(coordinate.get("horizontalCRS", "")),
                str(coordinate.get("verticalDatum", "")),
                str(coordinate.get("linearUnit", "")),
                str(coordinate.get("axisOrder", "XYZ"))),
            extent=Extent3D(_triple(extent.get("minimum"), "extent.minimum"),
                            _triple(extent.get("maximum"), "extent.maximum"),
                            _triple(extent.get("baseCellSize"), "extent.baseCellSize")),
            sources=tuple(SourceReference(
                str(item.get("sourceId", "")), str(item.get("authority", "")),
                str(item.get("title", "")), str(item.get("canonicalUrl", "")),
                str(item.get("accessDate", "")), str(item.get("scope", "")))
                for item in data.get("sources", [])),
            units=tuple(GeologicalUnit(
                str(item.get("unitId", "")), str(item.get("name", "")),
                int(item.get("orderIndex", -1)), tuple(item.get("sourceIds", [])),
                item.get("normalizedLithology"), str(item.get("termStatus", "Unverified")))
                for item in data.get("units", [])),
            events=tuple(GeologicalEvent(
                str(item.get("eventId", "")), EventType(item.get("eventType")),
                int(item.get("orderIndex", -1)), tuple(item.get("sourceIds", [])),
                tuple(item.get("affectedUnitIds", [])), dict(item.get("parameters", {})))
                for item in data.get("events", [])),
            relations=tuple(TopologyRelation(
                str(item.get("relationId", "")), RelationType(item.get("relationType")),
                str(item.get("sourceId", "")), str(item.get("targetId", "")),
                tuple(item.get("evidenceSourceIds", [])), float(item.get("confidence", -1)))
                for item in data.get("relations", [])))

    def validate_schema(self) -> dict:
        errors = []
        if not self.project_name.strip():
            errors.append({"code": "MissingProjectName"})
        if "synthetic" not in self.synthetic_disclosure.lower() and "疑似" not in self.synthetic_disclosure:
            errors.append({"code": "MissingSyntheticDisclosure"})
        if not self.regional_profile_id.strip():
            errors.append({"code": "MissingRegionalProfile"})
        if not self.sources:
            errors.append({"code": "NoSources"})
        if not self.units:
            errors.append({"code": "NoGeologicalUnits"})
        errors.extend(self.coordinate_reference.validate())
        errors.extend(self.extent.validate())
        for collection in (self.sources, self.units, self.events, self.relations):
            for item in collection:
                errors.extend(item.validate())
        for name, identifiers in (
                ("source", [item.source_id for item in self.sources]),
                ("unit", [item.unit_id for item in self.units]),
                ("event", [item.event_id for item in self.events]),
                ("relation", [item.relation_id for item in self.relations])):
            duplicates = sorted({item for item in identifiers if identifiers.count(item) > 1})
            for identifier in duplicates:
                errors.append({"code": "DuplicateIdentifier", "kind": name, "id": identifier})
        source_ids = {item.source_id for item in self.sources}
        for owner_type, owner_id, references in [
                *(('unit', item.unit_id, item.source_ids) for item in self.units),
                *(('event', item.event_id, item.source_ids) for item in self.events),
                *(('relation', item.relation_id, item.evidence_source_ids) for item in self.relations)]:
            for reference in references:
                if reference not in source_ids:
                    errors.append({"code": "UnknownSourceReference", "ownerType": owner_type,
                                   "ownerId": owner_id, "sourceId": reference})
        unit_ids = {item.unit_id for item in self.units}
        for event in self.events:
            for unit_id in event.affected_unit_ids:
                if unit_id not in unit_ids:
                    errors.append({"code": "UnknownAffectedUnit", "eventId": event.event_id,
                                   "unitId": unit_id})
        return {"passed": not errors, "errors": errors, "gate": "SchemaAndUnits"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "projectName": self.project_name,
            "syntheticDisclosure": self.synthetic_disclosure,
            "randomSeed": self.random_seed,
            "regionalProfileId": self.regional_profile_id,
            "coordinateReference": {
                "horizontalCRS": self.coordinate_reference.horizontal_crs,
                "verticalDatum": self.coordinate_reference.vertical_datum,
                "linearUnit": self.coordinate_reference.linear_unit,
                "axisOrder": self.coordinate_reference.axis_order},
            "extent": {"minimum": list(self.extent.minimum), "maximum": list(self.extent.maximum),
                       "baseCellSize": list(self.extent.base_cell_size)},
            "sources": [{"sourceId": item.source_id, "authority": item.authority,
                         "title": item.title, "canonicalUrl": item.canonical_url,
                         "accessDate": item.access_date, "scope": item.scope}
                        for item in self.sources],
            "units": [{"unitId": item.unit_id, "name": item.name,
                       "orderIndex": item.order_index, "sourceIds": list(item.source_ids),
                       "normalizedLithology": item.normalized_lithology,
                       "termStatus": item.term_status} for item in self.units],
            "events": [{"eventId": item.event_id, "eventType": item.event_type.value,
                        "orderIndex": item.order_index, "sourceIds": list(item.source_ids),
                        "affectedUnitIds": list(item.affected_unit_ids),
                        "parameters": item.parameters} for item in self.events],
            "relations": [{"relationId": item.relation_id,
                           "relationType": item.relation_type.value,
                           "sourceId": item.source_id, "targetId": item.target_id,
                           "evidenceSourceIds": list(item.evidence_source_ids),
                           "confidence": item.confidence} for item in self.relations]}


def load_config(path: str | Path) -> EngineConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("engine configuration root must be an object")
    return EngineConfig.from_dict(data)
