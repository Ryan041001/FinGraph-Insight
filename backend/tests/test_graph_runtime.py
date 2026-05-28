from app.models.api import GraphPayload
from app.services.graph_runtime import import_extraction_payload_runtime, import_graph_runtime
from app.services.graph_store import ImportStats


class FakeMemoryStore:
    def __init__(self):
        self.imported = []

    def import_graph(self, graph):
        self.imported.append(graph)
        return "memory_stats"


class FakeWriter:
    def __init__(self):
        self.graphs = []

    def write_graph(self, graph):
        self.graphs.append(graph)


def test_import_graph_runtime_uses_memory_only_by_default(monkeypatch):
    memory = FakeMemoryStore()
    writer = FakeWriter()

    monkeypatch.setattr("app.services.graph_runtime.settings.graph_backend", "memory")

    stats = import_graph_runtime(GraphPayload(nodes=[], edges=[]), memory_store=memory, neo4j_writer=writer)

    assert stats == "memory_stats"
    assert len(memory.imported) == 1
    assert writer.graphs == []


def test_import_graph_runtime_writes_through_to_neo4j_when_enabled(monkeypatch):
    memory = FakeMemoryStore()
    writer = FakeWriter()
    graph = GraphPayload(nodes=[], edges=[])

    monkeypatch.setattr("app.services.graph_runtime.settings.graph_backend", "neo4j")

    stats = import_graph_runtime(graph, memory_store=memory, neo4j_writer=writer)

    assert stats == "memory_stats"
    assert memory.imported == [graph]
    assert writer.graphs == [graph]


def test_import_extraction_payload_runtime_converts_payload_and_writes_to_neo4j(monkeypatch):
    memory = FakeMemoryStore()
    writer = FakeWriter()
    payload = {
        "document": {"content_hash": "doc_runtime_001"},
        "entities": [
            {"temp_id": "e1", "name": "星河数据", "type": "Company", "resolved_id": "company_xinghe"},
            {"temp_id": "e2", "name": "红杉资本", "type": "Institution", "resolved_id": "institution_sequoia"},
        ],
        "relationships": [
            {
                "temp_id": "r1",
                "head_temp_id": "e2",
                "relation": "INVESTED_IN",
                "tail_temp_id": "e1",
                "confidence": 0.91,
                "status": "confirmed",
                "evidence": "红杉资本投资星河数据",
            }
        ],
    }

    monkeypatch.setattr("app.services.graph_runtime.settings.graph_backend", "neo4j")

    stats = import_extraction_payload_runtime(payload, memory_store=memory, neo4j_writer=writer)

    assert stats == "memory_stats"
    assert len(memory.imported) == 1
    assert memory.imported[0].nodes[0].label == "星河数据"
    assert memory.imported[0].edges[0].type == "INVESTED_IN"
    assert writer.graphs == memory.imported
