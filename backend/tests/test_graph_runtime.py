from app.models.api import GraphPayload
from app.services.graph_runtime import import_graph_runtime


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
