from fastapi.testclient import TestClient

from app.main import app
from app.models.api import GraphPayload
from app.services.graph_store import ImportStats
from app.services.mock_data import sample_graph


client = TestClient(app)


def test_health_reports_scheduler_and_graph_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["neo4j"] in {"memory", "ok", "unavailable"}
    assert response.json()["scheduler"] in {"running", "configured", "disabled"}


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

    list_response = client.get("/jobs")
    assert list_response.status_code == 200
    job_ids = [job["job_run_id"] for job in list_response.json()["jobs"]]
    assert payload["job_run_id"] in job_ids

    detail_response = client.get(f"/jobs/{payload['job_run_id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["job_run_id"] == payload["job_run_id"]


def test_kline_endpoint_returns_market_contract():
    response = client.get("/market/kline/600000?market=A&period=daily")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_code"] == "600000"
    assert payload["market"] == "A"
    assert payload["data_source"] == "mock"
    assert payload["kline_data"][0]["date"]
    assert "events" in payload


def test_extract_uses_requested_text_entities_without_default_company_leak():
    response = client.post(
        "/extract",
        json={"text": "蓝海智能完成A轮融资，启明创投参与投资。"},
    )

    assert response.status_code == 200
    payload = response.json()
    entity_names = {entity["name"] for entity in payload["entities"]}
    rendered_payload = str(payload)

    assert {"蓝海智能", "启明创投"}.issubset(entity_names)
    assert "示例科技" not in rendered_payload


def test_graph_import_persists_confirmed_extraction_for_company_profile():
    extract_response = client.post(
        "/extract",
        json={"text": "星河数据完成B轮融资，红杉资本领投。"},
    )
    assert extract_response.status_code == 200

    import_response = client.post("/graph/import", json=extract_response.json())
    assert import_response.status_code == 200
    assert import_response.json()["relationships_created"] >= 1

    profile_response = client.get("/graph/company/星河数据")
    assert profile_response.status_code == 200
    profile = profile_response.json()
    edge_texts = [
        edge["provenance"].get("source_text", "")
        for edge in profile["graph"]["edges"]
    ]

    assert any("星河数据" in text for text in edge_texts)
    assert any(
        edge["type"] in {"INVESTED_IN", "RECEIVED_FUNDING"}
        for edge in profile["graph"]["edges"]
    )


def test_graph_import_route_uses_graph_runtime(monkeypatch):
    captured = {}

    def fake_runtime(payload):
        captured["payload"] = payload
        return ImportStats(
            nodes_created=1,
            nodes_matched=2,
            relationships_created=3,
            relationships_skipped=4,
        )

    monkeypatch.setattr("app.main.import_extraction_payload_runtime", fake_runtime)

    response = client.post("/graph/import", json={"entities": [], "relationships": []})

    assert response.status_code == 200
    assert captured["payload"] == {"entities": [], "relationships": []}
    assert response.json()["nodes_created"] == 1
    assert response.json()["nodes_matched"] == 2
    assert response.json()["relationships_created"] == 3
    assert response.json()["relationships_skipped"] == 4


def test_dataset_import_is_idempotent_and_populates_queryable_graph():
    first_response = client.post("/datasets/import", json={"dataset": "sample_graph"})
    second_response = client.post("/datasets/import", json={"dataset": "sample_graph"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first = first_response.json()
    second = second_response.json()

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert second["nodes_created"] == 0
    assert second["relationships_created"] == 0

    profile_response = client.get("/graph/company/示例科技")
    assert profile_response.status_code == 200
    assert profile_response.json()["graph"]["nodes"]


def test_financial_dataset_import_uses_dataset_loader(monkeypatch):
    monkeypatch.setattr("app.main.load_financial_dataset_directory", lambda path: sample_graph("导入企业"))

    response = client.post("/datasets/import", json={"dataset": "financial_datasets"})

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    profile_response = client.get("/graph/company/导入企业")
    assert profile_response.status_code == 200
    assert profile_response.json()["company"]["name"] == "导入企业"


def test_financial_dataset_import_uses_project_root_data_path(monkeypatch):
    seen_paths = []

    def fake_loader(path):
        seen_paths.append(path)
        return sample_graph("根目录数据企业")

    monkeypatch.setattr("app.main.load_financial_dataset_directory", fake_loader)

    response = client.post("/datasets/import", json={"dataset": "financial_datasets"})

    assert response.status_code == 200
    assert seen_paths
    assert "data" in str(seen_paths[0])
    assert "backend" not in str(seen_paths[0])
    profile_response = client.get("/graph/company/根目录数据企业")
    assert profile_response.status_code == 200
    assert profile_response.json()["company"]["name"] == "根目录数据企业"


def test_graph_path_returns_persisted_path_between_entities():
    extract_response = client.post(
        "/extract",
        json={"text": "路径公司完成A轮融资，路径资本领投。"},
    )
    assert extract_response.status_code == 200
    client.post("/graph/import", json=extract_response.json())

    response = client.get("/graph/path?source=路径资本&target=路径公司&max_depth=3")

    assert response.status_code == 200
    payload = response.json()
    assert payload["paths"]
    labels = {node["label"] for node in payload["paths"][0]["nodes"]}
    assert {"路径资本", "路径公司"}.issubset(labels)
