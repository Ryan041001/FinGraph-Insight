from __future__ import annotations

import re
from typing import Any

from app.models.api import GraphEdge, GraphNode, GraphPayload


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

    def write_graph(self, graph: GraphPayload) -> None:
        with self._driver.session() as session:
            for node in graph.nodes:
                query, parameters = build_merge_node_query(node)
                session.run(query, parameters)
            for edge in graph.edges:
                query, parameters = build_merge_relationship_query(edge)
                session.run(query, parameters)


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
