from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from app.models.api import GraphEdge, GraphNode, GraphPayload
from app.services.graph_store import ImportStats


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def safe_identifier(value: str) -> str:
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe Neo4j identifier: {value}")
    return value


def build_merge_node_query(node: GraphNode) -> tuple[str, dict[str, Any]]:
    label = safe_identifier(node.type)
    properties = _node_properties(node)
    query = f"""
MERGE (n:{label} {{id: $id}})
SET n += $properties
RETURN n
""".strip()
    return query, {"id": node.id, "properties": properties}


def build_merge_relationship_query(edge: GraphEdge) -> tuple[str, dict[str, Any]]:
    relationship_type = safe_identifier(edge.type)
    properties = _relationship_properties(edge)
    query = f"""
MATCH (source {{id: $source_id}})
MATCH (target {{id: $target_id}})
MERGE (source)-[r:{relationship_type} {{id: $id}}]->(target)
SET r += $properties
RETURN r
""".strip()
    return query, {
        "id": edge.id,
        "source_id": edge.source,
        "target_id": edge.target,
        "properties": properties,
    }


def build_node_constraint_query(label: str) -> str:
    safe_label = safe_identifier(label)
    return f"CREATE CONSTRAINT node_{safe_label}_id_unique IF NOT EXISTS FOR (n:{safe_label}) REQUIRE n.id IS UNIQUE"


def build_batch_node_query(label: str) -> str:
    safe_label = safe_identifier(label)
    return f"""
UNWIND $rows AS row
MERGE (n:{safe_label} {{id: row.id}})
SET n += row.properties
RETURN count(n) AS rows
""".strip()


def build_batch_relationship_query(relationship_type: str, source_label: str | None, target_label: str | None) -> str:
    safe_relationship_type = safe_identifier(relationship_type)
    source_pattern = _node_match_pattern("source", source_label)
    target_pattern = _node_match_pattern("target", target_label)
    return f"""
UNWIND $rows AS row
MATCH {source_pattern}
MATCH {target_pattern}
MERGE (source)-[r:{safe_relationship_type} {{id: row.id}}]->(target)
SET r += row.properties
RETURN count(r) AS rows
""".strip()


class Neo4jGraphWriter:
    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def write_graph(self, graph: GraphPayload) -> ImportStats:
        nodes_created = 0
        relationships_created = 0
        with self._driver.session() as session:
            node_groups = _group_nodes_by_type(graph.nodes)
            for label in node_groups:
                result = session.run(build_node_constraint_query(label))
                result.consume()
            for label, nodes in node_groups.items():
                result = session.run(
                    build_batch_node_query(label),
                    {"rows": [_node_row(node) for node in nodes]},
                )
                nodes_created += _summary_counter(result, "nodes_created")

            node_types = {node.id: node.type for node in graph.nodes}
            relationship_groups = _group_relationships_by_shape(graph.edges, node_types)
            for (relationship_type, source_label, target_label), edges in relationship_groups.items():
                result = session.run(
                    build_batch_relationship_query(relationship_type, source_label, target_label),
                    {"rows": [_relationship_row(edge) for edge in edges]},
                )
                relationships_created += _summary_counter(result, "relationships_created")
        return ImportStats(
            nodes_created=nodes_created,
            nodes_matched=max(0, len(graph.nodes) - nodes_created),
            relationships_created=relationships_created,
            relationships_skipped=max(0, len(graph.edges) - relationships_created),
        )


def _node_properties(node: GraphNode) -> dict[str, Any]:
    return {
        **_flat_properties(node.properties),
        "name": node.label,
        "label": node.label,
        "type": node.type,
        "risk_level": node.risk_level,
    }


def _relationship_properties(edge: GraphEdge) -> dict[str, Any]:
    return {
        **_flat_properties(edge.properties),
        **_flat_properties(edge.provenance),
        "label": edge.label,
        "confidence": edge.confidence,
        "status": edge.status,
    }


def _node_row(node: GraphNode) -> dict[str, Any]:
    return {"id": node.id, "properties": _node_properties(node)}


def _relationship_row(edge: GraphEdge) -> dict[str, Any]:
    return {
        "id": edge.id,
        "source_id": edge.source,
        "target_id": edge.target,
        "properties": _relationship_properties(edge),
    }


def _group_nodes_by_type(nodes: list[GraphNode]) -> dict[str, list[GraphNode]]:
    groups: dict[str, list[GraphNode]] = defaultdict(list)
    for node in nodes:
        groups[safe_identifier(node.type)].append(node)
    return dict(groups)


def _group_relationships_by_shape(
    edges: list[GraphEdge],
    node_types: dict[str, str],
) -> dict[tuple[str, str | None, str | None], list[GraphEdge]]:
    groups: dict[tuple[str, str | None, str | None], list[GraphEdge]] = defaultdict(list)
    for edge in edges:
        relationship_type = safe_identifier(edge.type)
        source_label = node_types.get(edge.source)
        target_label = node_types.get(edge.target)
        groups[(relationship_type, source_label, target_label)].append(edge)
    return dict(groups)


def _node_match_pattern(variable: str, label: str | None) -> str:
    if label:
        return f"({variable}:{safe_identifier(label)} {{id: row.{variable}_id}})"
    return f"({variable} {{id: row.{variable}_id}})"


def _flat_properties(properties: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in properties.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            flattened[key] = value
        elif isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) for item in value):
            flattened[key] = value
        else:
            flattened[key] = str(value)
    return flattened


def _summary_counter(result: Any, counter_name: str) -> int:
    consume = getattr(result, "consume", None)
    if not callable(consume):
        return 0
    summary = consume()
    counters = getattr(summary, "counters", None)
    return int(getattr(counters, counter_name, 0) or 0)
