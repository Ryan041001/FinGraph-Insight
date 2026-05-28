import pytest

from app.models.api import GraphEdge, GraphNode
from app.neo4j.connection import Neo4jConnectionConfig, check_neo4j_health, create_neo4j_driver
from app.neo4j.writer import build_merge_node_query, build_merge_relationship_query


def test_build_merge_node_query_uses_label_and_stable_id():
    node = GraphNode(
        id="company_001",
        label="示例科技",
        type="Company",
        properties={"industry": "金融科技"},
    )

    query, parameters = build_merge_node_query(node)

    assert "MERGE (n:Company {id: $id})" in query
    assert "SET n += $properties" in query
    assert parameters["id"] == "company_001"
    assert parameters["properties"]["name"] == "示例科技"
    assert parameters["properties"]["industry"] == "金融科技"


def test_build_merge_relationship_query_uses_relationship_id():
    edge = GraphEdge(
        id="rel_001",
        source="institution_001",
        target="event_001",
        type="INVESTED_IN",
        label="投资",
        confidence=0.92,
        properties={"role": "领投"},
        provenance={"source_text": "红杉资本领投。"},
    )

    query, parameters = build_merge_relationship_query(edge)

    assert "MATCH (source {id: $source_id})" in query
    assert "MATCH (target {id: $target_id})" in query
    assert "MERGE (source)-[r:INVESTED_IN {id: $id}]->(target)" in query
    assert parameters["source_id"] == "institution_001"
    assert parameters["target_id"] == "event_001"
    assert parameters["properties"]["confidence"] == 0.92
    assert parameters["properties"]["source_text"] == "红杉资本领投。"


def test_writer_rejects_unsafe_labels_and_relationship_types():
    unsafe_node = GraphNode(id="n1", label="bad", type="Company) DELETE n //")
    unsafe_edge = GraphEdge(
        id="r1",
        source="n1",
        target="n2",
        type="RELATED_TO] DELETE r //",
        label="bad",
    )

    with pytest.raises(ValueError, match="unsafe Neo4j identifier"):
        build_merge_node_query(unsafe_node)

    with pytest.raises(ValueError, match="unsafe Neo4j identifier"):
        build_merge_relationship_query(unsafe_edge)


def test_create_neo4j_driver_uses_configured_credentials(monkeypatch):
    captured = {}

    class FakeGraphDatabase:
        @staticmethod
        def driver(uri, auth):
            captured["uri"] = uri
            captured["auth"] = auth
            return "driver"

    monkeypatch.setattr("app.neo4j.connection.GraphDatabase", FakeGraphDatabase)
    config = Neo4jConnectionConfig(uri="bolt://neo4j:7687", user="neo4j", password="password")

    driver = create_neo4j_driver(config)

    assert driver == "driver"
    assert captured == {"uri": "bolt://neo4j:7687", "auth": ("neo4j", "password")}


def test_check_neo4j_health_reports_ok_and_unavailable():
    class HealthyDriver:
        def verify_connectivity(self):
            return None

    class FailingDriver:
        def verify_connectivity(self):
            raise RuntimeError("offline")

    assert check_neo4j_health(HealthyDriver()) == "ok"
    assert check_neo4j_health(FailingDriver()) == "unavailable"
    assert check_neo4j_health(None) == "unavailable"
