"""Typed geological topology graph and stage-one validation gates."""

from __future__ import annotations

from collections import defaultdict

from .config import EngineConfig
from .models import RelationType


class GeologicalTopologyGraph:
    def __init__(self, config: EngineConfig):
        self.config = config
        self.nodes = {item.unit_id: "Unit" for item in config.units}
        self.nodes.update({item.event_id: "Event" for item in config.events})
        self.relations = list(config.relations)

    @staticmethod
    def _cycle(nodes, adjacency):
        temporary, permanent = set(), set()

        def visit(node):
            if node in permanent:
                return None
            if node in temporary:
                return node
            temporary.add(node)
            for child in adjacency.get(node, []):
                found = visit(child)
                if found:
                    return found
            temporary.remove(node)
            permanent.add(node)
            return None

        for node in nodes:
            found = visit(node)
            if found:
                return found
        return None

    def validate(self) -> dict:
        errors = []
        for relation in self.relations:
            if relation.source_id not in self.nodes:
                errors.append({"code": "UnknownTopologyNode", "relationId": relation.relation_id,
                               "nodeId": relation.source_id})
            if relation.target_id not in self.nodes:
                errors.append({"code": "UnknownTopologyNode", "relationId": relation.relation_id,
                               "nodeId": relation.target_id})

        stratigraphic = defaultdict(list)
        containment = defaultdict(list)
        for relation in self.relations:
            if relation.source_id not in self.nodes or relation.target_id not in self.nodes:
                continue
            if relation.relation_type == RelationType.ABOVE:
                stratigraphic[relation.source_id].append(relation.target_id)
            elif relation.relation_type == RelationType.BELOW:
                stratigraphic[relation.target_id].append(relation.source_id)
            elif relation.relation_type == RelationType.CONTAINS:
                containment[relation.source_id].append(relation.target_id)
        cycle = self._cycle(self.nodes, stratigraphic)
        if cycle:
            errors.append({"code": "StratigraphicCycle", "nodeId": cycle})
        cycle = self._cycle(self.nodes, containment)
        if cycle:
            errors.append({"code": "ContainmentCycle", "nodeId": cycle})

        unit_orders = {unit.unit_id: unit.order_index for unit in self.config.units}
        for relation in self.relations:
            if relation.source_id not in unit_orders or relation.target_id not in unit_orders:
                continue
            if relation.relation_type == RelationType.ABOVE and not (
                    unit_orders[relation.source_id] < unit_orders[relation.target_id]):
                errors.append({"code": "OrderRelationConflict", "relationId": relation.relation_id})
            if relation.relation_type == RelationType.BELOW and not (
                    unit_orders[relation.source_id] > unit_orders[relation.target_id]):
                errors.append({"code": "OrderRelationConflict", "relationId": relation.relation_id})

        event_orders = [event.order_index for event in self.config.events]
        if len(event_orders) != len(set(event_orders)):
            errors.append({"code": "DuplicateEventOrder"})
        deposition_seen = False
        for event in sorted(self.config.events, key=lambda item: item.order_index):
            if event.event_type.value == "Deposition":
                deposition_seen = True
            elif event.event_type.value in {"Erosion", "Compaction", "Fold", "Fault"} and not deposition_seen:
                errors.append({"code": "EventBeforeMaterialExists", "eventId": event.event_id})

        return {"passed": not errors, "errors": errors, "gate": "TopologyAndChronology",
                "nodeCount": len(self.nodes), "relationCount": len(self.relations),
                "topologySignature": self.signature()}

    def signature(self) -> list[str]:
        return sorted(f"{item.source_id}|{item.relation_type.value}|{item.target_id}"
                      for item in self.relations)
