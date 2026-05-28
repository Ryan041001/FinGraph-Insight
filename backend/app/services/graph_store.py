from __future__ import annotations

import hashlib
from dataclasses import dataclass
from threading import RLock
from typing import Any

from app.models.api import GraphEdge, GraphNode, GraphPayload


def stable_id(*parts: object) -> str:
    normalized = "|".join(str(part).strip().lower() for part in parts if part is not None)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return digest


def node_id(entity_type: str, name: str) -> str:
    return f"{entity_type.lower()}_{stable_id(entity_type, name)}"


@dataclass(frozen=True)
class ImportStats:
    nodes_created: int
    nodes_matched: int
    relationships_created: int
    relationships_skipped: int


class InMemoryGraphStore:
    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._lock = RLock()

    def health_status(self) -> str:
        return "memory"

    def clear(self) -> None:
        with self._lock:
            self._nodes.clear()
            self._edges.clear()

    def import_graph(self, graph: GraphPayload) -> ImportStats:
        with self._lock:
            nodes_created = 0
            nodes_matched = 0
            relationships_created = 0
            relationships_skipped = 0

            for node in graph.nodes:
                if node.id in self._nodes:
                    nodes_matched += 1
                    self._nodes[node.id] = self._merge_node(self._nodes[node.id], node)
                else:
                    nodes_created += 1
                    self._nodes[node.id] = node

            for edge in graph.edges:
                if edge.id in self._edges:
                    relationships_skipped += 1
                    self._edges[edge.id] = self._merge_edge(self._edges[edge.id], edge)
                else:
                    relationships_created += 1
                    self._edges[edge.id] = edge

            return ImportStats(
                nodes_created=nodes_created,
                nodes_matched=nodes_matched,
                relationships_created=relationships_created,
                relationships_skipped=relationships_skipped,
            )

    def import_extraction_payload(self, payload: dict[str, Any]) -> ImportStats:
        entities = payload.get("entities", [])
        relationships = payload.get("relationships", [])
        document = payload.get("document", {})

        temp_to_node_id: dict[str, str] = {}
        nodes: list[GraphNode] = []

        for entity in entities:
            entity_type = str(entity.get("type", "Entity"))
            name = str(entity.get("name", "")).strip()
            if not name:
                continue

            resolved_id = str(entity.get("resolved_id") or node_id(entity_type, name))
            temp_id = str(entity.get("temp_id") or resolved_id)
            temp_to_node_id[temp_id] = resolved_id
            nodes.append(
                GraphNode(
                    id=resolved_id,
                    label=name,
                    type=entity_type,
                    properties={
                        "name": name,
                        "evidence": entity.get("evidence"),
                        "resolution_confidence": entity.get("resolution_confidence"),
                    },
                )
            )

        edges: list[GraphEdge] = []
        for relationship in relationships:
            confidence = float(relationship.get("confidence", 0))
            status = str(relationship.get("status", "pending_review"))
            if confidence < 0.5 or status == "rejected":
                continue

            source = temp_to_node_id.get(str(relationship.get("head_temp_id")))
            target = temp_to_node_id.get(str(relationship.get("tail_temp_id")))
            if not source or not target:
                continue

            relation_type = str(relationship.get("relation", "RELATED_TO"))
            evidence = str(relationship.get("evidence") or "")
            edge_id = f"rel_{stable_id(source, relation_type, target, evidence)}"
            edges.append(
                GraphEdge(
                    id=edge_id,
                    source=source,
                    target=target,
                    type=relation_type,
                    label=self._relation_label(relation_type),
                    confidence=confidence,
                    status=status,
                    properties=dict(relationship.get("attributes") or {}),
                    provenance={
                        "source_doc_id": document.get("content_hash"),
                        "source_text": evidence,
                        "source": "extraction",
                    },
                )
            )

        return self.import_graph(GraphPayload(nodes=nodes, edges=edges))

    def company_profile(self, name: str, depth: int = 2) -> dict[str, Any]:
        with self._lock:
            company = self._find_company(name)
            if company is None:
                return self._profile_from_graph(name, GraphPayload(nodes=[], edges=[]), depth)

            related_graph = self._subgraph_for_node(company.id, max_depth=max(1, min(depth, 3)))
            return self._profile_from_graph(company.label, related_graph, depth)

    def subgraph(self, entity: str, depth: int = 2, limit: int = 80) -> GraphPayload:
        with self._lock:
            start = self._find_node_by_label(entity)
            if start is None:
                return GraphPayload(nodes=[], edges=[])

            graph = self._subgraph_for_node(start.id, max_depth=max(1, min(depth, 3)))
            return GraphPayload(nodes=graph.nodes[:limit], edges=graph.edges[:limit])

    def all_graph(self) -> GraphPayload:
        with self._lock:
            return GraphPayload(nodes=list(self._nodes.values()), edges=list(self._edges.values()))

    def schema_tokens(self) -> tuple[set[str], set[str]]:
        with self._lock:
            labels = {node.type for node in self._nodes.values() if node.type}
            relationships = {edge.type for edge in self._edges.values() if edge.type}
            return labels, relationships

    def paths(self, source_label: str, target_label: str, max_depth: int = 4) -> list[dict[str, Any]]:
        with self._lock:
            source = self._find_node_by_label(source_label)
            target = self._find_node_by_label(target_label)
            if source is None or target is None:
                return []

            max_depth = max(1, min(max_depth, 4))
            queue: list[tuple[str, list[str], list[str]]] = [(source.id, [source.id], [])]
            visited_depth: dict[str, int] = {source.id: 0}

            while queue:
                current_id, node_path, edge_path = queue.pop(0)
                if current_id == target.id:
                    return [self._path_payload(node_path, edge_path)]
                if len(edge_path) >= max_depth:
                    continue

                for edge in self._edges.values():
                    neighbor = None
                    if edge.source == current_id:
                        neighbor = edge.target
                    elif edge.target == current_id:
                        neighbor = edge.source
                    if neighbor is None or neighbor in node_path:
                        continue
                    next_depth = len(edge_path) + 1
                    if visited_depth.get(neighbor, max_depth + 1) <= next_depth:
                        continue
                    visited_depth[neighbor] = next_depth
                    queue.append((neighbor, [*node_path, neighbor], [*edge_path, edge.id]))

            return []

    def _find_company(self, name: str) -> GraphNode | None:
        normalized = name.strip().lower()
        for node in self._nodes.values():
            if node.type == "Company" and node.label.strip().lower() == normalized:
                return node
        return None

    def _find_node_by_label(self, label: str) -> GraphNode | None:
        normalized = label.strip().lower()
        for node in self._nodes.values():
            if node.label.strip().lower() == normalized:
                return node
        return None

    def _subgraph_for_node(self, node_id: str, max_depth: int) -> GraphPayload:
        visited = {node_id}
        frontier = {node_id}
        selected_edges: dict[str, GraphEdge] = {}

        for _ in range(max_depth):
            next_frontier: set[str] = set()
            for edge in self._edges.values():
                touches_frontier = edge.source in frontier or edge.target in frontier
                if not touches_frontier:
                    continue
                selected_edges[edge.id] = edge
                for candidate in (edge.source, edge.target):
                    if candidate not in visited:
                        visited.add(candidate)
                        next_frontier.add(candidate)
            if not next_frontier:
                break
            frontier = next_frontier

        nodes = [self._nodes[node] for node in visited if node in self._nodes]
        return GraphPayload(nodes=nodes, edges=list(selected_edges.values()))

    def _path_payload(self, node_ids: list[str], edge_ids: list[str]) -> dict[str, Any]:
        return {
            "nodes": [self._nodes[node_id].model_dump() for node_id in node_ids if node_id in self._nodes],
            "edges": [self._edges[edge_id].model_dump() for edge_id in edge_ids if edge_id in self._edges],
            "length": len(edge_ids),
        }

    @staticmethod
    def _profile_from_graph(name: str, graph: GraphPayload, depth: int) -> dict[str, Any]:
        company = next((node for node in graph.nodes if node.type == "Company"), None)
        company_properties = company.properties if company else {}
        investor_names = [
            node.label
            for node in graph.nodes
            if node.type in {"Institution", "Company"} and node.label != name
        ]
        event_names = [node.label for node in graph.nodes if node.type == "Event"]
        return {
            "company": {
                "id": company.id if company else node_id("Company", name),
                "name": name,
                "industry": company_properties.get("industry", "未知"),
                "legal_representative": company_properties.get("legal_representative", "未知"),
            },
            "profile": {
                "shareholders": [],
                "investors": investor_names,
                "events": event_names,
                "hidden_relations": [],
                "risk_flags": [],
                "depth": depth,
            },
            "graph": graph.model_dump(),
        }

    @staticmethod
    def _merge_node(current: GraphNode, incoming: GraphNode) -> GraphNode:
        new_label = incoming.label or current.label
        new_type = incoming.type or current.type
        new_risk_level = incoming.risk_level or current.risk_level
        if incoming.properties:
            merged_properties = {**current.properties, **incoming.properties}
        else:
            merged_properties = current.properties
        if (
            new_label == current.label
            and new_type == current.type
            and new_risk_level == current.risk_level
            and merged_properties == current.properties
        ):
            return current
        return current.model_copy(
            update={
                "label": new_label,
                "type": new_type,
                "properties": merged_properties,
                "risk_level": new_risk_level,
            }
        )

    @staticmethod
    def _merge_edge(current: GraphEdge, incoming: GraphEdge) -> GraphEdge:
        new_confidence = max(current.confidence, incoming.confidence)
        new_status = incoming.status or current.status
        if incoming.properties:
            merged_properties = {**current.properties, **incoming.properties}
        else:
            merged_properties = current.properties
        if incoming.provenance:
            merged_provenance = {**current.provenance, **incoming.provenance}
        else:
            merged_provenance = current.provenance
        if (
            new_confidence == current.confidence
            and new_status == current.status
            and merged_properties == current.properties
            and merged_provenance == current.provenance
        ):
            return current
        return current.model_copy(
            update={
                "confidence": new_confidence,
                "status": new_status,
                "properties": merged_properties,
                "provenance": merged_provenance,
            }
        )

    @staticmethod
    def _relation_label(relation_type: str) -> str:
        labels = {
            "INVESTED_IN": "投资",
            "RECEIVED_FUNDING": "获得融资",
            "HOLDS_SHARES": "持股",
            "LEGAL_REP_OF": "法人",
        }
        return labels.get(relation_type, relation_type)


graph_store = InMemoryGraphStore()
