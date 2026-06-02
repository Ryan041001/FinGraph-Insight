import pytest

from app.models.api import GraphEdge, GraphNode, GraphPayload
from app.neo4j.connection import (
    Neo4jConnectionConfig,
    check_neo4j_health,
    close_neo4j_driver,
    create_neo4j_driver,
    get_neo4j_driver,
    reset_neo4j_driver_cache,
)
from app.neo4j.reader import Neo4jGraphReader, execute_readonly_cypher
from app.neo4j.writer import Neo4jGraphWriter, build_merge_node_query, build_merge_relationship_query


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


class FakeRecord:
    def __init__(self, data):
        self._data = data

    def data(self):
        return self._data

    def items(self):
        return self._data.items()


class FakeSession:
    def __init__(self, records):
        self.records = records
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def run(self, query, parameters=None):
        self.calls.append((query, parameters or {}))
        return [FakeRecord(record) for record in self.records]


class FakeDriver:
    def __init__(self, records):
        self.session_instance = FakeSession(records)

    def session(self):
        return self.session_instance


class FakeSummaryCounter:
    def __init__(self, nodes_created=0, relationships_created=0):
        self.nodes_created = nodes_created
        self.relationships_created = relationships_created


class FakeResult:
    def __init__(self, nodes_created=0, relationships_created=0):
        self._counters = FakeSummaryCounter(nodes_created=nodes_created, relationships_created=relationships_created)

    def consume(self):
        class Summary:
            counters = self._counters

        return Summary()


class FakeCountingSession:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def run(self, query, parameters=None):
        self.calls.append((query, parameters or {}))
        return self._results.pop(0)


class FakeCountingDriver:
    def __init__(self, results):
        self.session_instance = FakeCountingSession(results)

    def session(self):
        return self.session_instance


def test_neo4j_reader_builds_company_profile_from_real_records():
    driver = FakeDriver(
        [
            {
                "nodes": [
                    {
                        "id": "company_bangsheng",
                        "labels": ["Company"],
                        "properties": {"name": "邦盛科技", "industry": "金融科技", "legal_representative": "王明"},
                    },
                    {
                        "id": "event_bangsheng_c",
                        "labels": ["Event"],
                        "properties": {"name": "邦盛科技C轮融资事件", "round": "C轮"},
                    },
                ],
                "relationships": [
                    {
                        "id": "rel_bangsheng_c",
                        "source": "company_bangsheng",
                        "target": "event_bangsheng_c",
                        "type": "RECEIVED_FUNDING",
                        "properties": {"label": "获得融资", "source_text": "邦盛科技C轮获得国投创业投资"},
                    }
                ],
            }
        ]
    )

    profile = Neo4jGraphReader(driver).company_profile("邦盛科技", depth=2)

    assert profile["company"]["name"] == "邦盛科技"
    assert profile["company"]["industry"] == "金融科技"
    assert profile["profile"]["events"] == ["邦盛科技C轮融资事件"]
    assert profile["graph"]["edges"][0]["type"] == "RECEIVED_FUNDING"
    query, parameters = driver.session_instance.calls[0]
    assert "[*0..2]" in query
    assert parameters["entity"] == "邦盛科技"


def test_neo4j_reader_missing_company_does_not_fall_back_to_first_company():
    driver = FakeDriver(
        [
            {
                "nodes": [
                    {
                        "id": "company_bangsheng",
                        "labels": ["Company"],
                        "properties": {"name": "邦盛科技", "industry": "金融科技"},
                    },
                    {
                        "id": "event_bangsheng_c",
                        "labels": ["Event"],
                        "properties": {"name": "邦盛科技C轮融资事件"},
                    },
                ],
                "relationships": [],
            }
        ]
    )

    profile = Neo4jGraphReader(driver).company_profile("宇树科技", depth=2)

    assert profile["company"]["name"] == "宇树科技"
    assert profile["graph"]["nodes"] == []
    assert profile["graph"]["edges"] == []
    assert profile["profile"]["events"] == []


def test_neo4j_reader_returns_paths_from_real_records():
    driver = FakeDriver(
        [
            {
                "nodes": [
                    {"id": "institution_gt", "labels": ["Institution"], "properties": {"name": "国投创业"}},
                    {"id": "company_bangsheng", "labels": ["Company"], "properties": {"name": "邦盛科技"}},
                ],
                "relationships": [
                    {
                        "id": "rel_path",
                        "source": "institution_gt",
                        "target": "company_bangsheng",
                        "type": "INVESTED_IN",
                        "properties": {"label": "投资"},
                    }
                ],
                "length": 1,
            }
        ]
    )

    paths = Neo4jGraphReader(driver).paths("国投创业", "邦盛科技", max_depth=3)

    assert paths[0]["length"] == 1
    assert paths[0]["nodes"][0]["label"] == "国投创业"
    query, parameters = driver.session_instance.calls[0]
    assert "[*1..3]" in query
    assert parameters == {"source": "国投创业", "target": "邦盛科技"}


def test_neo4j_writer_returns_native_creation_counts():
    graph = GraphPayload(
        nodes=[
            GraphNode(id="company_bangsheng", label="邦盛科技", type="Company"),
            GraphNode(id="event_bangsheng", label="邦盛科技C轮融资事件", type="Event"),
        ],
        edges=[
            GraphEdge(
                id="rel_bangsheng",
                source="company_bangsheng",
                target="event_bangsheng",
                type="RECEIVED_FUNDING",
                label="获得融资",
            )
        ],
    )
    driver = FakeCountingDriver(
        [
            FakeResult(),
            FakeResult(),
            FakeResult(nodes_created=1),
            FakeResult(nodes_created=0),
            FakeResult(relationships_created=1),
        ]
    )

    stats = Neo4jGraphWriter(driver).write_graph(graph)

    assert stats.nodes_created == 1
    assert stats.nodes_matched == 1
    assert stats.relationships_created == 1
    assert stats.relationships_skipped == 0


def test_neo4j_writer_batches_large_dataset_writes_by_label_and_relationship_shape():
    graph = GraphPayload(
        nodes=[
            GraphNode(id="company_bangsheng", label="邦盛科技", type="Company"),
            GraphNode(id="company_yushu", label="宇树科技", type="Company"),
            GraphNode(id="event_bangsheng", label="邦盛科技C轮融资事件", type="Event"),
        ],
        edges=[
            GraphEdge(
                id="rel_bangsheng_1",
                source="company_bangsheng",
                target="event_bangsheng",
                type="RECEIVED_FUNDING",
                label="获得融资",
            ),
            GraphEdge(
                id="rel_bangsheng_2",
                source="company_yushu",
                target="event_bangsheng",
                type="RECEIVED_FUNDING",
                label="获得融资",
            ),
        ],
    )
    driver = FakeCountingDriver(
        [
            FakeResult(),
            FakeResult(),
            FakeResult(nodes_created=2),
            FakeResult(nodes_created=1),
            FakeResult(relationships_created=2),
        ]
    )

    stats = Neo4jGraphWriter(driver).write_graph(graph)

    calls = driver.session_instance.calls
    constraint_calls = [call for call in calls if call[0].startswith("CREATE CONSTRAINT")]
    node_batch_calls = [call for call in calls if "UNWIND $rows AS row" in call[0] and "MERGE (n:" in call[0]]
    relationship_batch_calls = [call for call in calls if "UNWIND $rows AS row" in call[0] and "MERGE (source)-[r:" in call[0]]

    assert len(constraint_calls) == 2
    assert len(node_batch_calls) == 2
    assert len(relationship_batch_calls) == 1
    assert len(node_batch_calls[0][1]["rows"]) == 2
    assert len(relationship_batch_calls[0][1]["rows"]) == 2
    assert stats.nodes_created == 3
    assert stats.nodes_matched == 0
    assert stats.relationships_created == 2
    assert stats.relationships_skipped == 0


def test_reader_collects_native_neo4j_path_objects():
    from neo4j.graph import Graph, Node, Path

    graph = Graph()
    investor = Node(
        graph,
        "node-investor",
        1,
        ["Institution"],
        {"id": "institution_gt", "name": "国投创业"},
    )
    company = Node(
        graph,
        "node-company",
        2,
        ["Company"],
        {"id": "company_bangsheng", "name": "邦盛科技"},
    )
    relationship_type = graph.relationship_type("INVESTED_IN")
    relationship = relationship_type(graph, "rel-path", 3, {"id": "rel_path", "label": "投资"})
    relationship._start_node = investor
    relationship._end_node = company

    driver = FakeDriver([{"path": Path(investor, relationship)}])

    paths = Neo4jGraphReader(driver).paths("国投创业", "邦盛科技", max_depth=3)

    assert paths[0]["length"] == 1
    assert [node["label"] for node in paths[0]["nodes"]] == ["国投创业", "邦盛科技"]
    assert paths[0]["edges"][0]["source"] == "institution_gt"
    assert paths[0]["edges"][0]["target"] == "company_bangsheng"


def test_execute_readonly_cypher_returns_table_and_graph_payload():
    driver = FakeDriver(
        [
            {
                "company": "邦盛科技",
                "node": {"id": "company_bangsheng", "labels": ["Company"], "properties": {"name": "邦盛科技"}},
            }
        ]
    )

    result = execute_readonly_cypher(driver, "MATCH (c:Company) RETURN c.name AS company, c AS node LIMIT 10")

    assert result["table"]["columns"] == ["company", "node"]
    assert result["table"]["rows"][0][0] == "邦盛科技"
    assert result["graph"]["nodes"][0]["label"] == "邦盛科技"


def test_get_neo4j_driver_returns_cached_singleton(monkeypatch):
    reset_neo4j_driver_cache()
    call_count = {"value": 0}

    def fake_create(config=None):
        call_count["value"] += 1
        return object()

    monkeypatch.setattr("app.neo4j.connection.create_neo4j_driver", fake_create)

    first = get_neo4j_driver()
    second = get_neo4j_driver()

    assert first is second
    assert call_count["value"] == 1


def test_close_neo4j_driver_closes_and_clears_cache(monkeypatch):
    reset_neo4j_driver_cache()
    closed = {"value": False}

    class FakeDriverWithClose:
        def close(self):
            closed["value"] = True

    monkeypatch.setattr("app.neo4j.connection.create_neo4j_driver", lambda config=None: FakeDriverWithClose())

    driver = get_neo4j_driver()
    assert isinstance(driver, FakeDriverWithClose)
    close_neo4j_driver()

    assert closed["value"] is True

    next_driver = get_neo4j_driver()
    assert next_driver is not driver
