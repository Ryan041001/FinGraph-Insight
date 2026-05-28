from app.services.graph_rag_service import answer_with_hybrid_context
from app.services.mock_data import sample_graph
from app.services.vector_store import InMemoryVectorStore, vector_store
from tests.test_api_contract import client


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
    graph = sample_graph("星河数据")

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


def test_graph_rag_route_uses_indexed_document_context():
    vector_store.clear()

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
    assert payload["document_context"]
    assert "年度订阅服务" in payload["answer"]
