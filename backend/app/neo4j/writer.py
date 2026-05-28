from __future__ import annotations

import re
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
    properties = {
        **_flat_properties(node.properties),
        "name": node.label,
        "label": node.label,
        "type": node.type,
        "risk_level": node.risk_level,
    }
    query = f"""
MERGE (n:{label} {{id: $id}})
SET n += $properties
RETURN n
""".strip()
    return query, {"id": node.id, "properties": properties}


def build_merge_relationship_query(edge: GraphEdge) -> tuple[str, dict[str, Any]]:
    relationship_type = safe_identifier(edge.type)
    properties = {
        **_flat_properties(edge.properties),
        **_flat_properties(edge.provenance),
        "label": edge.label,
        "confidence": edge.confidence,
        "status": edge.status,
    }
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


class Neo4jGraphWriter:
    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def write_graph(self, graph: GraphPayload) -> ImportStats:
        nodes_created = 0
        relationships_created = 0
        with self._driver.session() as session:
            for node in graph.nodes:
                query, parameters = build_merge_node_query(node)
                result = session.run(query, parameters)
                nodes_created += _summary_counter(result, "nodes_created")
            for edge in graph.edges:
                query, parameters = build_merge_relationship_query(edge)
                result = session.run(query, parameters)
                relationships_created += _summary_counter(result, "relationships_created")
        return ImportStats(
            nodes_created=nodes_created,
            nodes_matched=max(0, len(graph.nodes) - nodes_created),
            relationships_created=relationships_created,
            relationships_skipped=max(0, len(graph.edges) - relationships_created),
        )


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
