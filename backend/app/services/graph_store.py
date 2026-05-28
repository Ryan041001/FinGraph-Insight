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
            results: list[dict[str, Any]] = []
            shortest_length: int | None = None

            while queue:
                current_id, node_path, edge_path = queue.pop(0)
                if current_id == target.id and edge_path:
                    if shortest_length is None:
                        shortest_length = len(edge_path)
                    if len(edge_path) <= shortest_length:
                        results.append(self._path_payload(node_path, edge_path))
                    if len(results) >= 10:
                        break
                    continue
                if shortest_length is not None and len(edge_path) >= shortest_length:
                    continue
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
                    queue.append((neighbor, [*node_path, neighbor], [*edge_path, edge.id]))

            return results

    def _find_company(self, name: str) -> GraphNode | None:
        normalized = name.strip().lower()
        if not normalized:
            return None
        for node in self._nodes.values():
            if node.type == "Company" and node.label.strip().lower() == normalized:
                return node
        for node in self._nodes.values():
            if node.type == "Company" and normalized in node.label.strip().lower():
                return node
        return None

    def _find_node_by_label(self, label: str) -> GraphNode | None:
        normalized = label.strip().lower()
        if not normalized:
            return None
        for node in self._nodes.values():
            if node.label.strip().lower() == normalized:
                return node
        for node in self._nodes.values():
            if normalized in node.label.strip().lower():
                return node
        return None

    def search_companies(self, query: str, limit: int = 20) -> list[GraphNode]:
        with self._lock:
            normalized = query.strip().lower()
            companies = [node for node in self._nodes.values() if node.type == "Company"]
            if not normalized:
                return companies[:limit]

            exact: list[GraphNode] = []
            prefix: list[GraphNode] = []
            contains: list[GraphNode] = []
            for node in companies:
                label = node.label.strip().lower()
                if not label:
                    continue
                if label == normalized:
                    exact.append(node)
                elif label.startswith(normalized):
                    prefix.append(node)
                elif normalized in label:
                    contains.append(node)
            return (exact + prefix + contains)[:limit]

    def events_for_company(self, name: str, limit: int = 20) -> list[GraphNode]:
        with self._lock:
            company = self._find_company(name)
            if company is None:
                return []
            event_ids: list[str] = []
            for edge in self._edges.values():
                if edge.source == company.id and edge.target in self._nodes:
                    candidate = self._nodes[edge.target]
                    if candidate.type == "Event":
                        event_ids.append(candidate.id)
                elif edge.target == company.id and edge.source in self._nodes:
                    candidate = self._nodes[edge.source]
                    if candidate.type == "Event":
                        event_ids.append(candidate.id)
            seen: set[str] = set()
            events: list[GraphNode] = []
            for eid in event_ids:
                if eid in seen:
                    continue
                seen.add(eid)
                events.append(self._nodes[eid])
                if len(events) >= limit:
                    break
            return events

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
        nodes = [self._nodes[node_id].model_dump() for node_id in node_ids if node_id in self._nodes]
        edges = [self._edges[edge_id].model_dump() for edge_id in edge_ids if edge_id in self._edges]
        return {
            "nodes": nodes,
            "edges": edges,
            "length": len(edge_ids),
            "summary": self._summarize_path(nodes, edges),
        }

    @staticmethod
    def _summarize_path(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
        relationship_counts: dict[str, int] = {}
        for edge in edges:
            etype = edge.get("type", "")
            if etype:
                relationship_counts[etype] = relationship_counts.get(etype, 0) + 1
        intermediate_nodes = nodes[1:-1] if len(nodes) > 2 else []
        intermediate_events = [
            {"id": node["id"], "label": node["label"], "properties": node.get("properties", {})}
            for node in intermediate_nodes
            if node.get("type") == "Event"
        ]
        intermediate_actors = [
            {"id": node["id"], "label": node["label"], "type": node.get("type", "")}
            for node in intermediate_nodes
            if node.get("type") in {"Institution", "Company"}
        ]
        return {
            "relationship_counts": relationship_counts,
            "intermediate_events": intermediate_events,
            "intermediate_actors": intermediate_actors,
            "hop_count": len(edges),
        }

    def common_investors(self, company_names: list[str], limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            resolved = [(name, self._find_company(name)) for name in company_names]
            present = [(name, node) for name, node in resolved if node is not None]
            if len(present) < 2 or len(present) != len(resolved):
                return []

            company_to_events: dict[str, set[str]] = {}
            for name, node in present:
                event_ids: set[str] = set()
                for edge in self._edges.values():
                    if edge.type != "RECEIVED_FUNDING":
                        continue
                    if edge.source == node.id and edge.target in self._nodes and self._nodes[edge.target].type == "Event":
                        event_ids.add(edge.target)
                company_to_events[node.id] = event_ids

            investor_to_company_events: dict[str, dict[str, set[str]]] = {}
            for edge in self._edges.values():
                if edge.type != "INVESTED_IN":
                    continue
                investor_id = edge.source
                event_id = edge.target
                if event_id not in self._nodes:
                    continue
                for company_node_id, event_ids in company_to_events.items():
                    if event_id in event_ids:
                        bucket = investor_to_company_events.setdefault(investor_id, {})
                        bucket.setdefault(company_node_id, set()).add(event_id)

            results: list[dict[str, Any]] = []
            present_ids = {node.id for _, node in present}
            for investor_id, company_event_map in investor_to_company_events.items():
                if not present_ids.issubset(company_event_map.keys()):
                    continue
                investor_node = self._nodes.get(investor_id)
                if investor_node is None:
                    continue
                shared_events: list[dict[str, Any]] = []
                for event_id_set in company_event_map.values():
                    for event_id in event_id_set:
                        event_node = self._nodes.get(event_id)
                        if event_node is None:
                            continue
                        shared_events.append(
                            {
                                "id": event_node.id,
                                "label": event_node.label,
                                "round": event_node.properties.get("round", ""),
                                "date": event_node.properties.get("date", ""),
                            }
                        )
                results.append(
                    {
                        "investor": {
                            "id": investor_node.id,
                            "name": investor_node.label,
                            "type": investor_node.type,
                        },
                        "shared_company_count": len(present_ids),
                        "shared_events": shared_events,
                    }
                )

            results.sort(key=lambda item: -len(item["shared_events"]))
            return results[:limit]

    @staticmethod
    def _profile_from_graph(name: str, graph: GraphPayload, depth: int) -> dict[str, Any]:
        from app.services.risk_analyzer import analyze_company_risks

        company = next((node for node in graph.nodes if node.type == "Company"), None)
        company_properties = company.properties if company else {}
        investor_names = [
            node.label
            for node in graph.nodes
            if node.type in {"Institution", "Company"} and node.label != name
        ]
        event_names = [node.label for node in graph.nodes if node.type == "Event"]
        risk_flags = analyze_company_risks(name, graph)
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
                "risk_flags": risk_flags,
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
