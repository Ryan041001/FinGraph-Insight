from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_reports_scheduler_and_graph_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "neo4j": "mock",
        "scheduler": "mock",
    }


def test_company_profile_returns_graph_contract():
    response = client.get("/graph/company/示例科技")

    assert response.status_code == 200
    payload = response.json()
    assert payload["company"]["name"] == "示例科技"
    assert "nodes" in payload["graph"]
    assert "edges" in payload["graph"]


def test_company_profile_evidence_uses_requested_company_without_default_leaks():
    response = client.get("/graph/company/当前企业")

    assert response.status_code == 200
    payload = response.json()
    evidence_texts = [
        edge["provenance"]["source_text"]
        for edge in payload["graph"]["edges"]
    ]

    assert evidence_texts
    assert any("当前企业" in text for text in evidence_texts)
    assert all("示例科技" not in text for text in evidence_texts)


def test_graph_rag_returns_product_safe_answer_for_requested_company():
    response = client.post(
        "/qa/graph-rag",
        json={"question": "当前企业：这家公司有哪些需要关注的关联关系？"},
    )

    assert response.status_code == 200
    payload = response.json()
    rendered_payload = str(payload)

    assert "当前企业" in payload["answer"]
    assert all(word not in rendered_payload for word in ["示例", "样例", "演示", "doc_demo"])
    assert all("source_doc_id" not in citation for citation in payload["citations"])
    assert any(
        "当前企业" in edge["provenance"]["source_text"]
        for edge in payload["supporting_graph"]["edges"]
    )


def test_text2cypher_rejects_write_query_intent():
    response = client.post(
        "/qa/text2cypher",
        json={"question": "删除所有节点"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "unsafe_cypher"


def test_manual_update_job_returns_log_contract():
    response = client.post("/jobs/akshare/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert "job_run_id" in payload
    assert "new_documents" in payload


def test_kline_endpoint_returns_market_contract():
    response = client.get("/market/kline/600000?market=A&period=daily")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_code"] == "600000"
    assert payload["market"] == "A"
    assert payload["data_source"] == "mock"
    assert payload["kline_data"][0]["date"]
    assert "events" in payload
