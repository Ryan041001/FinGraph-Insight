from __future__ import annotations

from typing import Any

from app.models.api import GraphEdge, GraphNode, GraphPayload
from app.services.graph_store import node_id


class Neo4jGraphReader:
    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def company_profile(self, name: str, depth: int = 2) -> dict[str, Any]:
        graph = self.subgraph(name, depth=depth)
        company = next((node for node in graph.nodes if node.type == "Company" and node.label == name), None)
        if company is None:
            company = next((node for node in graph.nodes if node.type == "Company"), None)
        properties = company.properties if company else {}
        return {
            "company": {
                "id": company.id if company else node_id("Company", name),
                "name": company.label if company else name,
                "industry": properties.get("industry", "未知"),
                "legal_representative": properties.get("legal_representative", "未知"),
            },
            "profile": {
                "shareholders": [],
                "investors": [
                    node.label
                    for node in graph.nodes
                    if node.type in {"Institution", "Company"} and node.label != (company.label if company else name)
                ],
                "events": [node.label for node in graph.nodes if node.type == "Event"],
                "hidden_relations": [],
                "risk_flags": [],
                "depth": depth,
            },
            "graph": graph.model_dump(),
        }

    def subgraph(self, entity: str, depth: int = 2, limit: int = 80) -> GraphPayload:
        bounded_depth = max(1, min(depth, 3))
        bounded_limit = max(1, min(limit, 500))
        query = f"""
MATCH path=(start {{name: $entity}})-[*0..{bounded_depth}]-(neighbor)
WITH collect(path)[0..$limit] AS paths
RETURN paths AS paths
""".strip()
        records = self._run(query, {"entity": entity, "limit": bounded_limit})
        return _graph_from_records(records)

    def paths(self, source: str, target: str, max_depth: int = 4) -> list[dict[str, Any]]:
        bounded_depth = max(1, min(max_depth, 4))
        query = f"""
MATCH path=(source {{name: $source}})-[*1..{bounded_depth}]-(target {{name: $target}})
RETURN path AS path
LIMIT 10
""".strip()
        records = self._run(query, {"source": source, "target": target})
        paths: list[dict[str, Any]] = []
        for record in records:
            graph = _graph_from_records([record])
            paths.append({"nodes": [node.model_dump() for node in graph.nodes], "edges": [edge.model_dump() for edge in graph.edges], "length": int(record.get("length", len(graph.edges)))})
        return paths

    def _run(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        with self._driver.session() as session:
            return [record.data() for record in session.run(query, parameters)]


def execute_readonly_cypher(driver: Any, cypher: str) -> dict[str, Any]:
    with driver.session() as session:
        records = [record.data() for record in session.run(cypher, {})]

    columns: list[str] = []
    rows: list[list[Any]] = []
    for record in records:
        if not columns:
            columns = list(record.keys())
        rows.append([_table_value(record.get(column)) for column in columns])

    return {
        "table": {"columns": columns, "rows": rows},
        "graph": _graph_from_records(records).model_dump(),
    }


def _graph_from_records(records: list[dict[str, Any]]) -> GraphPayload:
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}
    for record in records:
        for value in record.values():
            _collect_graph_value(value, nodes, edges)
    return GraphPayload(nodes=list(nodes.values()), edges=list(edges.values()))


def _collect_graph_value(value: Any, nodes: dict[str, GraphNode], edges: dict[str, GraphEdge]) -> None:
    if isinstance(value, dict):
        if "nodes" in value or "relationships" in value:
            for node in value.get("nodes", []):
                graph_node = _node_from_neo4j(node)
                nodes[graph_node.id] = graph_node
            for relationship in value.get("relationships", []):
                graph_edge = _edge_from_neo4j(relationship)
                edges[graph_edge.id] = graph_edge
            return
        if "labels" in value and "properties" in value:
            graph_node = _node_from_neo4j(value)
            nodes[graph_node.id] = graph_node
            return
        if "type" in value and "source" in value and "target" in value:
            graph_edge = _edge_from_neo4j(value)
            edges[graph_edge.id] = graph_edge
            return
        for nested in value.values():
            _collect_graph_value(nested, nodes, edges)
        return
    if isinstance(value, list):
        for item in value:
            _collect_graph_value(item, nodes, edges)


def _node_from_neo4j(value: Any) -> GraphNode:
    properties = _properties(value)
    labels = list(value.get("labels", [])) if isinstance(value, dict) else []
    node_type = labels[0] if labels else str(properties.get("type") or "Entity")
    node_id_value = str(value.get("id") or properties.get("id") or node_id(node_type, str(properties.get("name", ""))))
    label = str(properties.get("name") or properties.get("label") or node_id_value)
    return GraphNode(id=node_id_value, label=label, type=node_type, properties=properties, risk_level=str(properties.get("risk_level", "normal")))


def _edge_from_neo4j(value: Any) -> GraphEdge:
    properties = _properties(value)
    edge_id = str(value.get("id") or properties.get("id"))
    edge_type = str(value.get("type") or properties.get("type") or "RELATED_TO")
    return GraphEdge(
        id=edge_id,
        source=str(value.get("source") or value.get("start") or properties.get("source")),
        target=str(value.get("target") or value.get("end") or properties.get("target")),
        type=edge_type,
        label=str(properties.get("label") or edge_type),
        confidence=float(properties.get("confidence", 1.0)),
        status=str(properties.get("status", "confirmed")),
        properties={key: val for key, val in properties.items() if key not in {"label", "confidence", "status", "source_text", "source", "source_doc_id"}},
        provenance={key: val for key, val in properties.items() if key in {"source_text", "source", "source_doc_id"}},
    )


def _properties(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        raw = value.get("properties", value)
        if isinstance(raw, dict):
            return dict(raw)
    return {}


def _table_value(value: Any) -> Any:
    if isinstance(value, dict) and ("labels" in value or "properties" in value or "nodes" in value or "relationships" in value):
        return _properties(value) or value
    if isinstance(value, list):
        return [_table_value(item) for item in value]
    return value
