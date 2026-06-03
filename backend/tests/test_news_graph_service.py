from app.models.api import GraphPayload
from app.services.graph_store import graph_store
from app.services.news_graph_service import import_news_events_to_graph, news_events_to_graph


class FakeExtractionGateway:
    def __init__(self):
        self.calls = []

    def complete(self, *, task, messages, temperature=0.2, top_p=0.9, max_tokens=None, **kwargs):
        self.calls.append({"task": task, "messages": messages})
        return (
            '{"entities":['
            '{"name":"宇树科技","type":"Company","evidence":"宇树科技"},'
            '{"name":"四足机器人","type":"Industry","evidence":"四足机器人"}'
            '],"relationships":['
            '{"head":"宇树科技","relation":"涉及主题","tail":"四足机器人",'
            '"evidence":"宇树科技发布四足机器人新品","confidence":0.86}'
            '],"warnings":[]}'
        )


def test_news_events_to_graph_creates_company_event_topic_and_document_edges():
    graph = news_events_to_graph(
        "宇树科技",
        [
            {
                "event_type": "product",
                "topic": "机器人",
                "sentiment": "positive",
                "title": "宇树科技发布四足机器人新品",
                "date": "2026-06-01",
                "source_url": "https://example.com/unitree",
                "evidence": "宇树科技公开披露机器人产品进展。",
            }
        ],
    )

    labels = {node.label for node in graph.nodes}
    edge_types = {edge.type for edge in graph.edges}

    assert "宇树科技" in labels
    assert "宇树科技发布四足机器人新品" in labels
    assert "机器人" in labels
    assert "MENTIONED_IN" in edge_types
    assert "HAS_TOPIC" in edge_types
    assert "SUPPORTED_BY" in edge_types


def test_import_news_events_to_graph_merges_live_news_with_existing_dataset_graph(monkeypatch):
    graph_store.clear()
    graph_store.import_graph(
        GraphPayload(
            nodes=[],
            edges=[],
        )
    )
    monkeypatch.setattr("app.services.graph_runtime.settings.graph_backend", "memory")

    stats = import_news_events_to_graph(
        "宇树科技",
        [
            {
                "event_type": "product",
                "topic": "机器人",
                "sentiment": "positive",
                "title": "宇树科技发布四足机器人新品",
                "date": "2026-06-01",
                "source_url": "https://example.com/unitree",
                "evidence": "宇树科技公开披露机器人产品进展。",
            }
        ],
        gateway=FakeExtractionGateway(),
    )

    subgraph = graph_store.subgraph("宇树科技", depth=3)
    labels = {node.label for node in subgraph.nodes}
    edge_types = {edge.type for edge in subgraph.edges}

    assert stats.nodes_created >= 4
    assert "宇树科技" in labels
    assert "宇树科技发布四足机器人新品" in labels
    assert "机器人" in labels
    assert "HAS_TOPIC" in edge_types
    assert "MENTIONED_IN" in edge_types
