from app.models.api import GraphEdge, GraphNode, GraphPayload
from app.services.graph_rag_service import answer_with_hybrid_context
from app.services.hybrid_rag_service import answer_with_hybrid_rag
from app.services.graph_store import InMemoryGraphStore
from app.services.vector_store import InMemoryVectorStore, vector_store
from tests.graph_fixtures import funding_graph
from tests.test_api_contract import client


class FakeGateway:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        self.calls.append(
            {
                "task": task,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.content


class FailingGateway:
    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        raise RuntimeError("upstream unavailable")


def test_vector_store_indexes_chunks_and_ranks_relevant_documents():
    store = InMemoryVectorStore()

    indexed = store.add_document(
        doc_id="doc_xinghe_001",
        title="星河数据商业模式",
        text="星河数据主要提供企业级数据治理平台。公司通过订阅制软件和实施服务获得收入。",
        metadata={"source": "research_note"},
    )
    store.add_document(
        doc_id="doc_other_001",
        title="绿能科技产能规划",
        text="绿能科技扩建储能电池产线，预计新增产能五吉瓦时。",
        metadata={"source": "research_note"},
    )

    results = store.search("星河数据的商业模式是什么", top_k=2)

    assert indexed >= 1
    assert results
    assert results[0]["doc_id"] == "doc_xinghe_001"
    assert results[0]["score"] > 0
    assert "订阅制软件" in results[0]["text"]
    assert results[0]["metadata"]["source"] == "research_note"


def test_hybrid_graph_rag_returns_graph_and_document_context():
    store = InMemoryVectorStore()
    store.add_document(
        doc_id="doc_xinghe_002",
        title="星河数据业务说明",
        text="星河数据的商业模式包括数据治理订阅、私有化部署和运维服务。",
        metadata={"source": "manual_note"},
    )
    graph = funding_graph("星河数据")

    response = answer_with_hybrid_context(
        "星河数据有哪些融资关系，商业模式是什么？",
        graph,
        vector_store=store,
        top_k=3,
    )

    assert response["retrieval"]["mode"] == "hybrid"
    assert response["supporting_graph"]["nodes"]
    assert response["document_context"]
    assert response["document_context"][0]["doc_id"] == "doc_xinghe_002"
    assert "数据治理订阅" in response["answer"]
    assert any(citation["source"] == "manual_note" for citation in response["citations"])


def test_hybrid_rag_service_returns_graph_document_and_retrieval_contract():
    store = InMemoryVectorStore()
    graph = InMemoryGraphStore()
    graph.import_graph(
        GraphPayload(
            nodes=[
                GraphNode(id="company_xinghe", label="星河数据", type="Company", properties={"name": "星河数据"}),
                GraphNode(id="event_xinghe", label="星河数据B轮融资事件", type="Event", properties={"name": "星河数据B轮融资事件"}),
            ],
            edges=[
                GraphEdge(
                    id="rel_xinghe",
                    source="company_xinghe",
                    target="event_xinghe",
                    type="RECEIVED_FUNDING",
                    label="获得融资",
                    provenance={"source_text": "星河数据完成B轮融资。"},
                )
            ],
        )
    )
    store.add_document(
        doc_id="doc_hybrid_001",
        title="星河数据说明",
        text="星河数据通过数据治理订阅服务获得收入。",
        metadata={"source": "hybrid_test"},
    )

    response = answer_with_hybrid_rag(
        "星河数据的收入模式是什么？",
        graph_store=graph,
        vector_store=store,
        gateway=None,
    )

    assert response["retrieval"]["mode"] == "hybrid"
    assert response["supporting_graph"]["nodes"]
    assert response["document_context"]
    assert "数据治理订阅服务" in response["answer"]


def test_hybrid_rag_service_marks_successful_llm_answer_source():
    store = InMemoryVectorStore()
    store.add_document(
        doc_id="doc_hybrid_llm_001",
        title="星河数据说明",
        text="星河数据通过数据治理订阅服务获得收入。",
        metadata={"source": "hybrid_llm_test"},
    )
    gateway = FakeGateway('{"answer":"LLM基于图谱和文档回答。"}')

    response = answer_with_hybrid_rag(
        "星河数据的收入模式是什么？",
        vector_store=store,
        gateway=gateway,
    )

    assert response["answer"] == "LLM基于图谱和文档回答。"
    assert response["retrieval"]["llm_used"] is True
    assert response["retrieval"]["answer_source"] == "llm"
    assert len(gateway.calls) == 1


def test_graph_rag_route_uses_indexed_document_context(monkeypatch):
    vector_store.clear()
    gateway = FakeGateway('{"answer":"路径企业通过年度订阅服务获得收入。"}')
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: gateway)

    index_response = client.post(
        "/rag/documents",
        json={
            "doc_id": "doc_route_001",
            "title": "路径企业说明",
            "text": "路径企业通过供应链风控平台和年度订阅服务获得收入。",
            "metadata": {"source": "route_test"},
        },
    )
    qa_response = client.post(
        "/qa/graph-rag",
        json={"question": "路径企业的收入模式是什么？"},
    )

    assert index_response.status_code == 200
    assert index_response.json()["chunks_indexed"] >= 1
    assert qa_response.status_code == 200
    payload = qa_response.json()
    assert payload["retrieval"]["mode"] == "hybrid"
    assert payload["retrieval"]["llm_used"] is True
    assert payload["document_context"]
    assert "年度订阅服务" in payload["answer"]


def test_hybrid_rag_route_returns_indexed_document_context(monkeypatch):
    vector_store.clear()
    gateway = FakeGateway('{"answer":"路径企业通过年度订阅服务获得收入。"}')
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: gateway)

    index_response = client.post(
        "/rag/documents",
        json={
            "doc_id": "doc_hybrid_route_001",
            "title": "路径企业说明",
            "text": "路径企业通过供应链风控平台和年度订阅服务获得收入。",
            "metadata": {"source": "hybrid_route_test"},
        },
    )
    qa_response = client.post(
        "/qa/hybrid-rag",
        json={"question": "路径企业的收入模式是什么？"},
    )

    assert index_response.status_code == 200
    assert qa_response.status_code == 200
    payload = qa_response.json()
    assert payload["retrieval"]["mode"] == "hybrid"
    assert payload["retrieval"]["llm_used"] is True
    assert payload["document_context"]
    assert "年度订阅服务" in payload["answer"]


def test_hybrid_rag_route_calls_llm_when_enabled(monkeypatch):
    vector_store.clear()
    gateway = FakeGateway('{"answer":"路由已调用LLM。"}')

    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: gateway)

    response = client.post(
        "/qa/hybrid-rag",
        json={"question": "路径企业的收入模式是什么？"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "路由已调用LLM。"
    assert response.json()["retrieval"]["llm_used"] is True
    assert len(gateway.calls) == 1


def test_hybrid_rag_route_reports_llm_error_instead_of_fallback(monkeypatch):
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: FailingGateway())

    response = client.post(
        "/qa/hybrid-rag",
        json={"question": "路径企业的收入模式是什么？"},
    )

    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "llm_error"
