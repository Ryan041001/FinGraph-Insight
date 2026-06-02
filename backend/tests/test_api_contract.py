import time

from fastapi.testclient import TestClient

from app.main import app
from app.models.api import JobRun
from app.models.api import GraphPayload
from app.models.api import GraphEdge, GraphNode
from app.services.graph_store import ImportStats
from app.services.graph_store import graph_store


client = TestClient(app)


class FakeGateway:
    def __init__(self, content: str) -> None:
        self.content = content

    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        return self.content


class FailingGateway:
    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        raise TimeoutError("upstream timeout")


class StreamingGateway:
    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        return '{"answer":"非流式回答"}'

    def stream_complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        yield "第一段"
        yield "第二段"


class DelayedStreamingGateway:
    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        return '{"answer":"延迟回答"}'

    def stream_complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        time.sleep(0.03)
        yield "延迟段"


class CapturingStreamingGateway:
    def __init__(self):
        self.messages = []

    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        self.messages = messages
        return '{"answer":"非流式回答"}'

    def stream_complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        self.messages = messages
        yield "HTML 输出测试"


def test_health_reports_scheduler_and_graph_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["neo4j"] in {"memory", "ok", "unavailable"}
    assert response.json()["scheduler"] in {"running", "configured", "disabled"}


def test_dataset_candidate_paths_cover_container_and_repo_layouts(tmp_path):
    from app import main

    container_app_file = tmp_path / "app" / "main.py"
    container_app_file.parent.mkdir(parents=True)
    container_app_file.write_text("", encoding="utf-8")

    repo_app_file = tmp_path / "repo" / "backend" / "app" / "main.py"
    repo_app_file.parent.mkdir(parents=True)
    repo_app_file.write_text("", encoding="utf-8")

    container_paths = list(main._dataset_candidate_paths(container_app_file))
    repo_paths = list(main._dataset_candidate_paths(repo_app_file))

    assert tmp_path / "data" / "raw" / "FinancialDatasets" in container_paths
    assert tmp_path / "repo" / "data" / "raw" / "FinancialDatasets" in repo_paths


def test_health_checks_real_neo4j_connectivity_when_backend_enabled(monkeypatch):
    monkeypatch.setattr("app.main.settings.graph_backend", "neo4j")
    monkeypatch.setattr("app.main.graph_store.health_status", lambda: "memory")
    monkeypatch.setattr("app.main.get_neo4j_driver", lambda: object(), raising=False)
    monkeypatch.setattr("app.main.check_neo4j_health", lambda driver: "ok", raising=False)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["neo4j"] == "ok"


def test_company_profile_uses_neo4j_reader_when_backend_enabled(monkeypatch):
    monkeypatch.setattr("app.services.graph_query_service.settings.graph_backend", "neo4j")
    monkeypatch.setattr("app.services.graph_query_service.get_neo4j_driver", lambda: "driver")

    class FakeReader:
        def __init__(self, driver):
            self.driver = driver

        def company_profile(self, name, depth=2):
            return {
                "company": {"id": "company_bangsheng", "name": name, "industry": "金融科技", "legal_representative": "王明"},
                "profile": {"events": ["邦盛科技C轮融资事件"], "investors": [], "shareholders": [], "hidden_relations": [], "risk_flags": [], "depth": depth},
                "graph": {"nodes": [{"id": "company_bangsheng", "label": name, "type": "Company", "properties": {}, "risk_level": "normal"}], "edges": []},
            }

    monkeypatch.setattr("app.services.graph_query_service.Neo4jGraphReader", FakeReader)

    response = client.get("/graph/company/邦盛科技")

    assert response.status_code == 200
    assert response.json()["company"]["name"] == "邦盛科技"
    assert response.json()["profile"]["events"] == ["邦盛科技C轮融资事件"]


def test_company_profile_returns_graph_contract():
    graph_store.clear()

    response = client.get("/graph/company/不存在的真实企业")

    assert response.status_code == 200
    payload = response.json()
    assert payload["company"]["name"] == "不存在的真实企业"
    assert "nodes" in payload["graph"]
    assert "edges" in payload["graph"]
    assert payload["graph"]["nodes"] == []
    assert payload["graph"]["edges"] == []
    assert payload["profile"]["events"] == []


def test_company_profile_has_no_sample_evidence_when_company_is_missing():
    graph_store.clear()

    response = client.get("/graph/company/当前企业")

    assert response.status_code == 200
    payload = response.json()
    rendered_payload = str(payload)

    assert payload["graph"]["edges"] == []
    assert payload["graph"]["nodes"] == []
    assert all(word not in rendered_payload for word in ["示例", "样例", "演示", "doc_demo"])


def test_graph_rag_returns_product_safe_answer_for_requested_company(monkeypatch):
    graph_store.clear()
    graph_store.import_graph(
        GraphPayload(
            nodes=[
                GraphNode(id="company_current", label="当前企业", type="Company", properties={"name": "当前企业"}),
                GraphNode(id="event_current", label="当前企业A轮融资事件", type="Event", properties={"name": "当前企业A轮融资事件"}),
            ],
            edges=[
                GraphEdge(
                    id="rel_current",
                    source="company_current",
                    target="event_current",
                    type="RECEIVED_FUNDING",
                    label="获得融资",
                    provenance={"source_text": "当前企业完成A轮融资。"},
                )
            ],
        )
    )
    monkeypatch.setattr(
        "app.main.HttpLLMGateway",
        lambda: FakeGateway('{"answer":"当前企业存在融资和投资方关联关系。"}'),
    )

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


def test_manual_update_job_returns_log_contract(monkeypatch):
    jobs = {}

    def fake_job():
        job = JobRun(
            job_run_id="job_contract_test",
            status="success",
            started_at="2026-05-28T00:00:00",
            finished_at="2026-05-28T00:00:01",
            new_documents=1,
            new_entities=2,
            new_relationships=1,
            failed_items=0,
        )
        jobs[job.job_run_id] = job
        return job

    monkeypatch.setattr("app.main.start_akshare_update_async", fake_job)
    monkeypatch.setattr("app.main.list_job_runs", lambda: list(jobs.values()))
    monkeypatch.setattr("app.main.get_job_run", lambda job_run_id: jobs.get(job_run_id))

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


def test_kline_endpoint_returns_market_contract(monkeypatch):
    monkeypatch.setattr("app.main.settings.market_live_enabled", True)

    def fake_kline(**kwargs):
        return {
            "stock_code": kwargs["stock_code"],
            "market": kwargs["market"],
            "display_code": "600000.SH",
            "company_name": "浦发银行",
            "period": kwargs["period"],
            "adjust": kwargs["adjust"],
            "cached": False,
            "data_source": "akshare",
            "start_date": kwargs["start_date"],
            "end_date": kwargs["end_date"],
            "kline_data": [{"date": "2024-03-15", "open": 7.23, "close": 7.45, "high": 7.5, "low": 7.18, "volume": 123, "amount": 456.7}],
            "events": [],
        }

    monkeypatch.setattr("app.main.build_kline_response", fake_kline)

    response = client.get("/market/kline/600000?market=A&period=daily")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_code"] == "600000"
    assert payload["market"] == "A"
    assert payload["data_source"] == "akshare"
    assert payload["kline_data"][0]["date"]
    assert payload["events"] == []


def test_kline_endpoint_reports_market_error_without_mock_fallback(monkeypatch):
    monkeypatch.setattr("app.main.settings.market_live_enabled", True)

    def failing_kline(**kwargs):
        raise RuntimeError("akshare unavailable")

    monkeypatch.setattr("app.main.build_kline_response", failing_kline)

    response = client.get("/market/kline/600000?market=A&period=daily")

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "market_data_error"


def test_extract_uses_requested_text_entities_without_default_company_leak(monkeypatch):
    monkeypatch.setattr(
        "app.main.HttpLLMGateway",
        lambda: FakeGateway(
            '{"entities":[{"name":"蓝海智能","type":"Company","evidence":"蓝海智能完成A轮融资"},'
            '{"name":"启明创投","type":"Institution","evidence":"启明创投参与投资"}],'
            '"relationships":[],"warnings":[]}'
        ),
    )

    response = client.post(
        "/extract",
        json={
            "text": "蓝海智能完成A轮融资，启明创投参与投资。",
            "options": {"self_refine": False, "judge": False},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    entity_names = {entity["name"] for entity in payload["entities"]}
    rendered_payload = str(payload)

    assert {"蓝海智能", "启明创投"}.issubset(entity_names)
    assert "示例科技" not in rendered_payload


def test_extract_route_rejects_mock_mode_for_business_runtime(monkeypatch):
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: FailingGateway())

    response = client.post(
        "/extract",
        json={
            "text": "端测云链科技有限公司完成Pre-A轮融资，端测高榕资本跟投。",
            "options": {"mock": True, "self_refine": False, "judge": False},
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "mock_disabled"


def test_graph_import_persists_confirmed_extraction_for_company_profile(monkeypatch):
    monkeypatch.setattr(
        "app.main.HttpLLMGateway",
        lambda: FakeGateway(
            '{"entities":[{"name":"星河数据","type":"Company","evidence":"星河数据完成B轮融资"},'
            '{"name":"红杉资本","type":"Institution","evidence":"红杉资本领投"},'
            '{"name":"B轮融资","type":"Event","evidence":"B轮融资"}],'
            '"relationships":[{"head":"红杉资本","relation":"INVESTED_IN","tail":"B轮融资",'
            '"evidence":"红杉资本领投星河数据B轮融资","confidence":0.91},'
            '{"head":"星河数据","relation":"RECEIVED_FUNDING","tail":"B轮融资",'
            '"evidence":"星河数据完成B轮融资","confidence":0.91}],'
            '"warnings":[]}'
        ),
    )

    extract_response = client.post(
        "/extract",
        json={
            "text": "星河数据完成B轮融资，红杉资本领投。",
            "options": {"self_refine": False, "judge": False},
        },
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


def test_text2cypher_route_executes_readonly_cypher_when_neo4j_enabled(monkeypatch):
    captured = {}

    monkeypatch.setattr("app.main.settings.graph_backend", "neo4j")
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: FakeGateway('{"cypher":"MATCH (c:Company) RETURN c.name AS company"}'))
    monkeypatch.setattr("app.main.get_neo4j_driver", lambda: "driver")

    def fake_execute(driver, cypher):
        captured["driver"] = driver
        captured["cypher"] = cypher
        return {
            "table": {"columns": ["company"], "rows": [["邦盛科技"]]},
            "graph": {"nodes": [], "edges": []},
        }

    monkeypatch.setattr("app.main.execute_readonly_cypher", fake_execute)

    response = client.post("/qa/text2cypher", json={"question": "查询所有公司"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["table"]["rows"] == [["邦盛科技"]]
    assert captured["driver"] == "driver"
    assert captured["cypher"] == "MATCH (c:Company) RETURN c.name AS company LIMIT 50"


def test_text2cypher_route_falls_back_to_safe_template_when_llm_times_out(monkeypatch):
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: FailingGateway())

    response = client.post("/qa/text2cypher", json={"question": "查询所有公司"})

    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "llm_error"


def test_unified_qa_uses_public_evidence_for_missing_local_company(monkeypatch):
    graph_store.clear()
    captured: dict[str, object] = {}

    monkeypatch.setattr("app.main.settings.graph_backend", "memory")
    monkeypatch.setattr("app.main.generate_cypher_with_llm", lambda question, gateway: ("MATCH (c:Company) RETURN c.name AS company LIMIT 50", ["readonly"]))
    monkeypatch.setattr(
        "app.main.answer_with_hybrid_rag",
        lambda question, entity, gateway: {
            "answer": "暂无可用证据线索。",
            "supporting_graph": {"nodes": [], "edges": []},
            "citations": [],
            "document_context": [],
            "retrieval": {"mode": "hybrid", "graph_nodes": 0, "graph_edges": 0, "document_chunks": 0},
        },
    )

    def fake_build_stock_analysis(payload, news_gateway=None):
        captured["payload"] = payload
        return {
            "target": {"stock_code": "", "company_name": payload["company_name"]},
            "fundamentals": {"industry": "机器人", "data_time": "local-cache"},
            "news_events": [
                {
                    "event_type": "public_info",
                    "sentiment": "neutral",
                    "title": "宇树科技发布四足机器人新品",
                    "date": "2026-06-01",
                    "source_url": "https://example.com/unitree",
                    "evidence": "宇树科技公开披露机器人产品进展。",
                }
            ],
            "subgraph": {"nodes": [], "edges": []},
            "analysis": {
                "summary": "宇树科技当前研判基于可用证据线索生成。",
                "missing_data": [],
                "disclaimer": "本结果仅用于课程项目演示和研究辅助，不构成投资建议。",
            },
        }

    monkeypatch.setattr("app.main.build_stock_analysis", fake_build_stock_analysis)

    response = client.post(
        "/qa/unified",
        json={"question": "有什么风险？", "entity": "宇树科技"},
    )

    assert response.status_code == 200
    payload = response.json()
    rendered = str(payload)
    assert captured["payload"]["company_name"] == "宇树科技"
    assert payload["document_context"]
    assert payload["retrieval"]["realtime_events"] == 1
    assert "宇树科技" in payload["answer"]
    assert "宇树科技" in rendered
    assert "邦盛科技" not in rendered


def test_unified_qa_memory_mode_returns_real_query_graph_for_audit_visualization(monkeypatch):
    graph_store.clear()
    company = GraphNode(
        id="company_xinghe",
        label="星河数据",
        type="Company",
        properties={"industry": "金融科技"},
    )
    event = GraphNode(
        id="event_xinghe_b",
        label="星河数据B轮融资事件",
        type="Event",
        properties={"round": "B轮", "amount": "3000万元"},
    )
    investor = GraphNode(
        id="investor_sequoia",
        label="红杉资本",
        type="Institution",
        properties={},
    )
    graph_store.import_graph(
        GraphPayload(
            nodes=[company, event, investor],
            edges=[
                GraphEdge(
                    id="rel_xinghe_received",
                    source=company.id,
                    target=event.id,
                    type="RECEIVED_FUNDING",
                    label="获得融资",
                    confidence=0.93,
                    properties={},
                ),
                GraphEdge(
                    id="rel_sequoia_invested",
                    source=investor.id,
                    target=event.id,
                    type="INVESTED_IN",
                    label="投资",
                    confidence=0.93,
                    properties={},
                ),
            ],
        )
    )

    monkeypatch.setattr("app.main.settings.graph_backend", "memory")
    monkeypatch.setattr(
        "app.main.generate_cypher_with_llm",
        lambda question, gateway: (
            'MATCH (c:Company {name: "星河数据"})-[:RECEIVED_FUNDING]->(e:Event)<-[:INVESTED_IN]-(inv) RETURN c, e, inv LIMIT 50',
            ["read_only", "limit_checked"],
        ),
    )
    monkeypatch.setattr(
        "app.main.answer_with_hybrid_rag",
        lambda question, entity, gateway: {
            "answer": "星河数据已获得红杉资本投资。",
            "supporting_graph": graph_store.subgraph(entity).model_dump(),
            "citations": [],
            "document_context": [],
            "retrieval": {"mode": "hybrid"},
        },
    )

    response = client.post(
        "/qa/unified",
        json={"question": "这家公司有哪些投资方？", "entity": "星河数据"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["text2cypher"] == "ok"
    assert {node["label"] for node in payload["graph"]["nodes"]} >= {"星河数据", "红杉资本", "星河数据B轮融资事件"}
    assert {edge["label"] for edge in payload["graph"]["edges"]} >= {"获得融资", "投资"}
    assert payload["table"]["columns"] == ["节点", "类型", "风险等级"]
    assert ["星河数据", "Company", "normal"] in payload["table"]["rows"]
    assert any("本地图谱执行查询" in message for message in payload["messages"])


def test_unified_qa_neo4j_mode_enriches_node_only_audit_result_with_entity_subgraph(monkeypatch):
    graph_store.clear()
    company = GraphNode(
        id="company_xinghe",
        label="星河数据",
        type="Company",
        properties={"name": "星河数据"},
    )
    event = GraphNode(
        id="event_xinghe_b",
        label="星河数据B轮融资事件",
        type="Event",
        properties={"name": "星河数据B轮融资事件"},
    )
    edge = GraphEdge(
        id="rel_xinghe_b",
        source=company.id,
        target=event.id,
        type="RECEIVED_FUNDING",
        label="获得融资",
    )
    graph_store.import_graph(GraphPayload(nodes=[company, event], edges=[edge]))

    monkeypatch.setattr("app.main.settings.graph_backend", "neo4j")
    monkeypatch.setattr(
        "app.main.generate_cypher_with_llm",
        lambda question, gateway: ("MATCH (c:Company {name: '星河数据'}) RETURN c LIMIT 50", ["readonly"]),
    )
    monkeypatch.setattr("app.main.get_neo4j_driver", lambda: "driver")
    monkeypatch.setattr(
        "app.main.execute_readonly_cypher",
        lambda driver, cypher: {
            "table": {"columns": ["节点"], "rows": [["星河数据"]]},
            "graph": {"nodes": [company.model_dump()], "edges": []},
        },
    )
    monkeypatch.setattr(
        "app.main.answer_with_hybrid_rag",
        lambda question, entity, gateway: {
            "answer": "星河数据存在融资事件。",
            "supporting_graph": {"nodes": [company.model_dump()], "edges": []},
            "citations": [],
            "document_context": [],
            "retrieval": {},
        },
    )

    response = client.post(
        "/qa/unified",
        json={"question": "这家公司有哪些风险点？", "entity": "星河数据"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["text2cypher"] == "ok"
    assert {node["label"] for node in payload["graph"]["nodes"]} >= {"星河数据", "星河数据B轮融资事件"}
    assert {edge["label"] for edge in payload["graph"]["edges"]} >= {"获得融资"}
    assert payload["table"]["rows"] == [["星河数据"]]
    assert any("Neo4j" in message for message in payload["messages"])


def test_unified_qa_adds_inline_html_evidence_table_when_llm_answer_is_plain_text(monkeypatch):
    graph_store.clear()
    company = GraphNode(id="company_xinghe", label="星河数据", type="Company")
    graph_store.import_graph(GraphPayload(nodes=[company], edges=[]))

    monkeypatch.setattr("app.main.settings.graph_backend", "memory")
    monkeypatch.setattr(
        "app.main.generate_cypher_with_llm",
        lambda question, gateway: ("MATCH (c:Company {name: '星河数据'}) RETURN c LIMIT 50", ["readonly"]),
    )
    monkeypatch.setattr(
        "app.main.answer_with_hybrid_rag",
        lambda question, entity, gateway: {
            "answer": "星河数据当前未发现高风险证据。",
            "supporting_graph": graph_store.subgraph(entity).model_dump(),
            "citations": [],
            "document_context": [],
            "retrieval": {},
        },
    )

    response = client.post(
        "/qa/unified",
        json={"question": "这家公司有哪些风险点？", "entity": "星河数据"},
    )

    assert response.status_code == 200
    answer = response.json()["answer"]
    assert "星河数据当前未发现高风险证据。" in answer
    assert '<div class="qa-insight-card" style=' in answer
    assert '<table class="qa-evidence-table" style=' in answer
    assert 'border: 1px solid' in answer
    assert 'background:' in answer
    assert ">节点</th>" in answer
    assert ">星河数据</td>" in answer


def test_unified_qa_adds_evidence_table_when_llm_answer_has_html_list_without_table():
    from app.main import _ensure_inline_html_answer

    answer = _ensure_inline_html_answer(
        "<h2>风险点</h2><ul><li>当前未发现高风险标记。</li></ul>",
        {"columns": ["节点", "类型"], "rows": [["星河数据", "Company"]]},
    )

    assert "<ul><li>当前未发现高风险标记。</li></ul>" in answer
    assert '<table class="qa-evidence-table" style=' in answer
    assert ">星河数据</td>" in answer


def test_latest_stock_analysis_returns_cached_or_local_analysis_without_llm(monkeypatch):
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: FailingGateway())

    response = client.get("/analysis/stock/600000/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["target"]["stock_code"] == "600000"
    assert payload["analysis"]["disclaimer"] == "本结果仅用于课程项目演示和研究辅助，不构成投资建议。"


def test_stock_analysis_defaults_to_fast_local_contract_without_llm(monkeypatch):
    called = False

    def unexpected_gateway():
        nonlocal called
        called = True
        return FailingGateway()

    monkeypatch.setattr("app.main.HttpLLMGateway", unexpected_gateway)

    response = client.post(
        "/analysis/stock",
        json={"stock_code": "600000", "company_name": "端测云链科技有限公司"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert called is False
    assert payload["target"]["stock_code"] == "600000"
    assert payload["analysis"]["disclaimer"] == "本结果仅用于课程项目演示和研究辅助，不构成投资建议。"


def test_stock_analysis_refresh_news_reports_news_fallback(monkeypatch):
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: FailingGateway())

    response = client.post(
        "/analysis/stock",
        json={
            "stock_code": "600000",
            "company_name": "端测云链科技有限公司",
            "refresh_news": True,
        },
    )

    assert response.status_code == 200
    missing_data = response.json()["analysis"]["missing_data"]
    assert missing_data == ["部分信息暂未获取，已基于现有证据生成。"]


def test_manual_akshare_run_uses_real_update_path(monkeypatch):
    called = {}

    def fake_update():
        called["used"] = True
        return JobRun(
            job_run_id="job_real_update",
            status="success",
            started_at="2026-05-28T00:00:00",
            finished_at="2026-05-28T00:00:01",
            new_documents=1,
            new_entities=0,
            new_relationships=0,
            failed_items=0,
        )

    monkeypatch.setattr("app.main.start_akshare_update_async", fake_update)

    response = client.post("/jobs/akshare/run")

    assert response.status_code == 200
    payload = response.json()
    assert called["used"] is True
    assert payload["status"] == "success"
    assert payload["new_documents"] >= 1
    assert payload["failed_items"] == 0


def test_graph_rag_stream_returns_sse_events(monkeypatch):
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: StreamingGateway())

    response = client.post(
        "/qa/graph-rag/stream",
        json={"question": "端测云链科技有限公司：融资关系是什么？"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: metadata" in body
    assert "tool_calls" in body
    assert "event: delta" in body
    assert "第一段" in body
    assert "第二段" in body
    assert "event: done" in body


def test_graph_rag_stream_prompt_supports_bounded_html_fragments(monkeypatch):
    gateway = CapturingStreamingGateway()
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: gateway)

    response = client.post(
        "/qa/graph-rag/stream",
        json={"question": "端测云链科技有限公司：融资关系是什么？"},
    )

    assert response.status_code == 200
    system_prompt = gateway.messages[0]["content"]
    assert "<!-- html-render-start -->" in system_prompt
    assert "<!-- html-render-end -->" in system_prompt
    assert "禁止输出 <!DOCTYPE html>" in system_prompt
    assert "禁止 style 属性" in system_prompt
    assert "禁止输出 <!DOCTYPE html>" in system_prompt
    assert "禁止输出 <!DOCTYPE html>、<html>、<head>、<body>、<style>、<script>" in system_prompt
    assert "可以使用语义 class" in system_prompt


def test_graph_rag_stream_sends_ping_while_waiting_for_llm(monkeypatch):
    monkeypatch.setattr("app.main.SSE_HEARTBEAT_SECONDS", 0.01)
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: DelayedStreamingGateway())

    response = client.post(
        "/qa/graph-rag/stream",
        json={"question": "端测云链科技有限公司：融资关系是什么？"},
    )

    assert response.status_code == 200
    body = response.text
    assert "event: metadata" in body
    assert "event: ping" in body
    assert "event: delta" in body
    assert "延迟段" in body
    assert "event: done" in body


def test_hybrid_rag_stream_returns_sse_events(monkeypatch):
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: StreamingGateway())

    response = client.post(
        "/qa/hybrid-rag/stream",
        json={
            "question": "端测云链科技有限公司：融资金额是多少？",
            "entity": "端测云链科技有限公司",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: metadata" in body
    assert "document_context" in body
    assert "tool_calls" in body
    assert "event: delta" in body
    assert "第一段" in body
    assert "第二段" in body
    assert "event: done" in body


def test_unified_qa_stream_returns_sse_events(monkeypatch):
    graph_store.clear()
    monkeypatch.setattr("app.main.settings.graph_backend", "memory")
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: StreamingGateway())
    monkeypatch.setattr(
        "app.main.generate_cypher_with_llm",
        lambda question, gateway: ("MATCH (c:Company) RETURN c.name AS company LIMIT 50", ["readonly"]),
    )
    monkeypatch.setattr(
        "app.main.answer_with_hybrid_rag",
        lambda question, entity, gateway: {
            "answer": "",
            "supporting_graph": {"nodes": [], "edges": []},
            "citations": [{"title": "证据线索", "source": "local"}],
            "document_context": [{"title": "宇树科技证据线索", "content": "宇树科技公开披露机器人产品进展。"}],
            "retrieval": {"mode": "hybrid", "graph_nodes": 0, "graph_edges": 0, "document_chunks": 1},
        },
    )

    response = client.post(
        "/qa/unified/stream",
        json={"question": "有什么风险？", "entity": "宇树科技"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: metadata" in body
    assert "document_context" in body
    assert "宇树科技证据线索" in body
    assert "event: delta" in body
    assert "第一段" in body
    assert "第二段" in body
    assert "event: done" in body


def test_stock_analysis_stream_returns_sse_events(monkeypatch):
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: StreamingGateway())

    response = client.post(
        "/analysis/stock/stream",
        json={"stock_code": "600000", "company_name": "端测云链科技有限公司"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: metadata" in body
    assert "端测云链科技有限公司" in body
    assert "tool_calls" in body
    assert "event: delta" in body
    assert "第一段" in body
    assert "event: done" in body


def test_metrics_extraction_requires_real_predictor_configuration():
    response = client.get("/metrics/extraction")

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "metrics_unavailable"


def test_dataset_import_is_idempotent_and_populates_queryable_graph(monkeypatch):
    graph_store.clear()
    real_graph = GraphPayload(
        nodes=[
            GraphNode(id="company_real_import", label="真实导入企业", type="Company", properties={"name": "真实导入企业"}),
            GraphNode(id="event_real_import", label="真实导入企业A轮融资事件", type="Event", properties={"name": "真实导入企业A轮融资事件"}),
        ],
        edges=[
            GraphEdge(
                id="rel_real_import",
                source="company_real_import",
                target="event_real_import",
                type="RECEIVED_FUNDING",
                label="获得融资",
                provenance={"source": "真实投资事件表", "source_text": "真实导入企业完成A轮融资。"},
            )
        ],
    )

    monkeypatch.setattr("app.main.load_financial_dataset_directory", lambda path: real_graph)

    first_response = client.post("/datasets/import", json={"dataset": "financial_datasets"})
    second_response = client.post("/datasets/import", json={"dataset": "financial_datasets"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first = first_response.json()
    second = second_response.json()

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert second["nodes_created"] == 0
    assert second["relationships_created"] == 0

    profile_response = client.get("/graph/company/真实导入企业")
    assert profile_response.status_code == 200
    assert profile_response.json()["graph"]["nodes"]


def test_financial_dataset_import_uses_dataset_loader(monkeypatch):
    graph_store.clear()
    monkeypatch.setattr(
        "app.main.load_financial_dataset_directory",
        lambda path: GraphPayload(
            nodes=[GraphNode(id="company_imported", label="导入企业", type="Company", properties={"name": "导入企业"})],
            edges=[],
        ),
    )

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
        return GraphPayload(
            nodes=[GraphNode(id="company_root_imported", label="根目录数据企业", type="Company", properties={"name": "根目录数据企业"})],
            edges=[],
        )

    monkeypatch.setattr("app.main.load_financial_dataset_directory", fake_loader)

    response = client.post("/datasets/import", json={"dataset": "financial_datasets"})

    assert response.status_code == 200
    assert seen_paths
    assert "data" in str(seen_paths[0])
    assert "backend" not in str(seen_paths[0])
    profile_response = client.get("/graph/company/根目录数据企业")
    assert profile_response.status_code == 200
    assert profile_response.json()["company"]["name"] == "根目录数据企业"


def test_graph_companies_search_returns_fuzzy_matches(monkeypatch):
    from app.services.graph_store import graph_store
    from app.models.api import GraphNode, GraphPayload

    graph_store.clear()
    graph_store.import_graph(
        GraphPayload(
            nodes=[
                GraphNode(id="company_search_1", label="蓝海智能科技", type="Company", properties={"name": "蓝海智能科技", "industry": "AI"}),
                GraphNode(id="company_search_2", label="蓝海资本", type="Company", properties={"name": "蓝海资本"}),
                GraphNode(id="company_search_3", label="高榕资本", type="Company", properties={"name": "高榕资本"}),
            ],
            edges=[],
        )
    )

    response = client.get("/graph/companies", params={"q": "蓝海", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    labels = [item["name"] for item in payload["companies"]]
    assert "蓝海智能科技" in labels
    assert "蓝海资本" in labels


def test_graph_companies_search_empty_query_returns_top_n():
    from app.services.graph_store import graph_store
    from app.models.api import GraphNode, GraphPayload

    graph_store.clear()
    graph_store.import_graph(
        GraphPayload(
            nodes=[
                GraphNode(id=f"company_empty_{i}", label=f"批量公司{i}", type="Company", properties={"name": f"批量公司{i}"})
                for i in range(5)
            ],
            edges=[],
        )
    )

    response = client.get("/graph/companies", params={"limit": 3})

    assert response.status_code == 200
    assert response.json()["total"] == 3


def test_company_profile_finds_partial_match():
    from app.services.graph_store import graph_store
    from app.models.api import GraphNode, GraphPayload

    graph_store.clear()
    graph_store.import_graph(
        GraphPayload(
            nodes=[GraphNode(id="company_full_1", label="邦盛科技股份有限公司", type="Company", properties={"name": "邦盛科技股份有限公司"})],
            edges=[],
        )
    )

    response = client.get("/graph/company/邦盛")

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert "邦盛" in payload["company"]["name"]


def test_graph_path_returns_multiple_paths_when_available():
    from app.services.graph_store import graph_store
    from app.models.api import GraphEdge, GraphNode, GraphPayload

    graph_store.clear()
    graph_store.import_graph(
        GraphPayload(
            nodes=[
                GraphNode(id="company_a", label="公司A", type="Company"),
                GraphNode(id="company_b", label="公司B", type="Company"),
                GraphNode(id="event_x", label="事件X", type="Event"),
                GraphNode(id="event_y", label="事件Y", type="Event"),
            ],
            edges=[
                GraphEdge(id="rel_ax", source="company_a", target="event_x", type="RECEIVED_FUNDING", label="获得融资"),
                GraphEdge(id="rel_bx", source="company_b", target="event_x", type="INVESTED_IN", label="投资"),
                GraphEdge(id="rel_ay", source="company_a", target="event_y", type="RECEIVED_FUNDING", label="获得融资"),
                GraphEdge(id="rel_by", source="company_b", target="event_y", type="INVESTED_IN", label="投资"),
            ],
        )
    )

    response = client.get("/graph/path", params={"source": "公司A", "target": "公司B", "max_depth": 3})

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert len(paths) >= 2

    first = paths[0]
    assert "summary" in first
    summary = first["summary"]
    assert summary["hop_count"] == first["length"]
    assert summary["relationship_counts"]
    assert any(event["label"].startswith("事件") for event in summary["intermediate_events"])


def test_graph_common_investors_returns_overlap_between_companies():
    from app.services.graph_store import graph_store
    from app.models.api import GraphEdge, GraphNode, GraphPayload

    graph_store.clear()
    graph_store.import_graph(
        GraphPayload(
            nodes=[
                GraphNode(id="company_alpha", label="阿尔法科技", type="Company"),
                GraphNode(id="company_beta", label="贝塔科技", type="Company"),
                GraphNode(id="company_gamma", label="伽马科技", type="Company"),
                GraphNode(id="event_alpha_a", label="阿尔法A轮", type="Event", properties={"round": "A轮", "date": "2023-01-01"}),
                GraphNode(id="event_beta_a", label="贝塔A轮", type="Event", properties={"round": "A轮", "date": "2023-05-01"}),
                GraphNode(id="event_gamma_a", label="伽马A轮", type="Event", properties={"round": "A轮", "date": "2023-08-01"}),
                GraphNode(id="institution_shared", label="共投资本", type="Institution"),
                GraphNode(id="institution_solo", label="独投资本", type="Institution"),
            ],
            edges=[
                GraphEdge(id="rel_alpha_a", source="company_alpha", target="event_alpha_a", type="RECEIVED_FUNDING", label="获得融资"),
                GraphEdge(id="rel_beta_a", source="company_beta", target="event_beta_a", type="RECEIVED_FUNDING", label="获得融资"),
                GraphEdge(id="rel_gamma_a", source="company_gamma", target="event_gamma_a", type="RECEIVED_FUNDING", label="获得融资"),
                GraphEdge(id="rel_shared_alpha", source="institution_shared", target="event_alpha_a", type="INVESTED_IN", label="投资"),
                GraphEdge(id="rel_shared_beta", source="institution_shared", target="event_beta_a", type="INVESTED_IN", label="投资"),
                GraphEdge(id="rel_solo_alpha", source="institution_solo", target="event_alpha_a", type="INVESTED_IN", label="投资"),
                GraphEdge(id="rel_shared_gamma", source="institution_shared", target="event_gamma_a", type="INVESTED_IN", label="投资"),
            ],
        )
    )

    response = client.get("/graph/common-investors", params={"companies": "阿尔法科技,贝塔科技"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["investors"][0]["investor"]["name"] == "共投资本"
    assert payload["investors"][0]["shared_company_count"] == 2

    triple = client.get("/graph/common-investors", params={"companies": "阿尔法科技,贝塔科技,伽马科技"})
    assert triple.json()["investors"][0]["investor"]["name"] == "共投资本"


def test_graph_common_investors_rejects_single_company():
    response = client.get("/graph/common-investors", params={"companies": "邦盛科技"})

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_input"


def test_kline_response_attaches_company_events(monkeypatch):
    from app.services.graph_store import graph_store
    from app.models.api import GraphNode, GraphPayload

    graph_store.clear()
    graph_store.import_graph(
        GraphPayload(
            nodes=[
                GraphNode(id="company_kline_test", label="测试上市公司", type="Company", properties={"name": "测试上市公司"}),
                GraphNode(
                    id="event_kline_funding",
                    label="测试上市公司A轮融资",
                    type="Event",
                    properties={"name": "测试上市公司A轮融资", "date": "2024-03-15", "round": "A轮", "amount": "1亿元"},
                ),
            ],
            edges=[
                {"id": "rel_kline_evt", "source": "company_kline_test", "target": "event_kline_funding",
                 "type": "RECEIVED_FUNDING", "label": "获得融资", "properties": {}, "provenance": {}}
            ],
        )
    )

    def fake_kline(**kwargs):
        return {
            "stock_code": "999001",
            "market": "A",
            "display_code": "999001",
            "company_name": "999001",
            "period": "daily",
            "adjust": "qfq",
            "cached": False,
            "data_source": "test",
            "start_date": None,
            "end_date": None,
            "kline_data": [{"date": "2024-03-15", "open": 1, "close": 2, "high": 3, "low": 0.5, "volume": 100, "amount": 0}],
            "events": [],
        }

    monkeypatch.setattr("app.main.build_kline_response", fake_kline)

    response = client.get("/market/kline/999001", params={"company_name": "测试上市公司"})

    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 1
    assert events[0]["date"] == "2024-03-15"
    assert events[0]["round"] == "A轮"


def test_question_entity_extraction_falls_back_to_graph_match(monkeypatch):
    from app.services.graph_store import graph_store
    from app.models.api import GraphEdge, GraphNode, GraphPayload

    graph_store.clear()
    graph_store.import_graph(
        GraphPayload(
            nodes=[
                GraphNode(id="company_fuzzy_q", label="量子云链科技", type="Company", properties={"name": "量子云链科技"}),
            ],
            edges=[],
        )
    )
    captured = {}

    def capture_gateway():
        class StreamingFake:
            def complete(self, **kwargs):
                return '{"answer":"ok"}'

            def stream_complete(self, **kwargs):
                captured["question"] = kwargs.get("messages", [{}, {}])[1].get("content", "")
                yield "ok"

        return StreamingFake()

    monkeypatch.setattr("app.main.HttpLLMGateway", capture_gateway)

    response = client.post("/qa/graph-rag/stream", json={"question": "量子云链科技最近有哪些融资？"})

    assert response.status_code == 200
    # 验证 SSE 已经使用了图谱里识别到的公司名
    assert "量子云链科技" in response.text


def test_akshare_run_returns_running_immediately_with_background_thread(monkeypatch):
    completed_event = {"value": False}

    def slow_fetcher():
        import time
        time.sleep(0.2)
        completed_event["value"] = True
        return []

    monkeypatch.setattr("app.services.scheduler_service.fetch_akshare_news", slow_fetcher)
    monkeypatch.setattr(
        "app.services.scheduler_service._default_extractor",
        lambda text: {"entities": [], "relationships": [], "warnings": []},
    )
    monkeypatch.setattr(
        "app.services.scheduler_service._default_judge",
        lambda payload: payload,
    )

    response = client.post("/jobs/akshare/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["finished_at"] is None
    assert completed_event["value"] is False


def test_graph_subgraph_rejects_invalid_depth_and_limit():
    invalid_depth = client.get("/graph/subgraph", params={"entity": "邦盛科技", "depth": -1})
    assert invalid_depth.status_code == 422
    assert invalid_depth.json()["error"] == "invalid_input"

    too_large_limit = client.get("/graph/subgraph", params={"entity": "邦盛科技", "limit": 9999})
    assert too_large_limit.status_code == 422
    assert any("limit" in field["field"] for field in too_large_limit.json()["fields"])


def test_market_kline_rejects_unsupported_period(monkeypatch):
    response = client.get("/market/kline/600000", params={"period": "yearly"})

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_input"
    assert any("period" in field["field"] for field in response.json()["fields"])


def test_preload_endpoint_reports_current_state():
    response = client.get("/preload")

    assert response.status_code == 200
    payload = response.json()
    assert "dataset_status" in payload
    assert payload["dataset_status"] in {"skipped", "running", "ready", "failed"}
    assert "akshare_status" in payload


def test_startup_preload_worker_imports_dataset(monkeypatch):
    from app.services.graph_store import graph_store
    from app.models.api import GraphNode, GraphPayload
    import app.main as main_module

    graph_store.clear()
    with main_module._PRELOAD_STATE_LOCK:
        main_module._PRELOAD_STATE.update({"dataset_status": "skipped", "akshare_status": "skipped", "error": None})

    fake_graph = GraphPayload(
        nodes=[GraphNode(id="company_preload_test", label="预加载公司", type="Company", properties={"name": "预加载公司"})],
        edges=[],
    )

    monkeypatch.setattr("app.main.settings.startup_preload_dataset", True)
    monkeypatch.setattr("app.main.settings.startup_refresh_akshare", False)
    monkeypatch.setattr("app.main._load_dataset_graph", lambda dataset: fake_graph)

    main_module._start_startup_preload()

    import time
    deadline = time.time() + 3
    while time.time() < deadline:
        snapshot = main_module._snapshot_preload_state()
        if snapshot["dataset_status"] in {"ready", "failed"}:
            break
        time.sleep(0.05)

    snapshot = main_module._snapshot_preload_state()
    assert snapshot["dataset_status"] == "ready", snapshot
    assert snapshot["dataset_nodes"] >= 1


def test_text2cypher_memory_mode_returns_note_instead_of_full_graph(monkeypatch):
    from app.services.graph_store import graph_store
    from app.models.api import GraphNode, GraphPayload

    graph_store.clear()
    bulk_nodes = [
        GraphNode(id=f"company_bulk_{i}", label=f"批量公司{i}", type="Company", properties={"name": f"批量公司{i}"})
        for i in range(50)
    ]
    graph_store.import_graph(GraphPayload(nodes=bulk_nodes, edges=[]))

    monkeypatch.setattr("app.main.settings.graph_backend", "memory")
    monkeypatch.setattr(
        "app.main.generate_cypher_with_llm",
        lambda question, gateway: ("MATCH (c:Company) RETURN c LIMIT 5", ["read_only", "limit_added"]),
    )
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: FakeGateway('{"cypher":"MATCH (c:Company) RETURN c"}'))

    response = client.post("/qa/text2cypher", json={"question": "查询所有公司"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["graph"]["nodes"] == []
    assert payload["graph"]["edges"] == []
    assert payload["cypher"].startswith("MATCH")
    assert "neo4j" in payload["note"].lower() or "Neo4j" in payload["note"]


def test_text2cypher_returns_json_response_on_validation_failure(monkeypatch):
    def reject(question, gateway):
        raise ValueError("生成的 Cypher 包含未知图谱标签 Foo，已拒绝执行。")

    monkeypatch.setattr("app.main.generate_cypher_with_llm", reject)
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: FakeGateway('{"cypher":"MATCH (f:Foo) RETURN f"}'))

    response = client.post("/qa/text2cypher", json={"question": "查询所有 Foo 节点"})

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"] == "unsafe_cypher"
    assert payload["cypher"] == ""
    assert "Foo" in payload["message"]


def test_validation_errors_use_unified_error_envelope():
    response = client.get("/graph/subgraph")

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "invalid_input"
    assert payload["message"]
    assert payload["fields"][0]["field"] == "query.entity"
    assert payload["fields"][0]["type"] == "missing"


def test_extract_rejects_blank_and_oversized_text():
    blank = client.post("/extract", json={"text": "   "})
    assert blank.status_code == 422
    assert blank.json()["error"] == "invalid_input"
    assert any("non-empty" in field["message"] for field in blank.json()["fields"])

    too_long = client.post("/extract", json={"text": "a" * 9000})
    assert too_long.status_code == 422
    assert too_long.json()["error"] == "invalid_input"
    assert any("8000" in field["message"] for field in too_long.json()["fields"])


def test_rag_documents_rejects_blank_and_oversized_text():
    blank = client.post("/rag/documents", json={"doc_id": "d1", "text": "   "})
    assert blank.status_code == 422
    assert blank.json()["error"] == "invalid_input"

    too_long = client.post("/rag/documents", json={"doc_id": "d1", "text": "a" * 50001})
    assert too_long.status_code == 422
    assert too_long.json()["error"] == "invalid_input"
    assert any("50000" in field["message"] for field in too_long.json()["fields"])


def test_company_endpoint_marks_missing_entities_with_found_false():
    from app.services.graph_store import graph_store

    graph_store.clear()
    response = client.get("/graph/company/不存在的测试公司EE99")

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is False
    assert payload["graph"]["nodes"] == []


def test_llm_error_message_is_sanitized_in_response(monkeypatch):
    class LeakyGateway:
        def complete(self, **kwargs):
            raise RuntimeError(
                "Client error '401 Unauthorized' for url 'https://ai.example.com/v1/chat/completions'"
            )

    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: LeakyGateway())

    response = client.post(
        "/extract",
        json={"text": "测试文本", "options": {"self_refine": False, "judge": False}},
    )

    assert response.status_code == 502
    message = response.json()["detail"]["message"]
    assert "https://ai.example.com" not in message
    assert "<llm endpoint>" in message


def test_dataset_loader_is_cached_across_imports(monkeypatch, tmp_path):
    from app.main import _DATASET_CACHE, _DATASET_CACHE_LOCK
    from app.models.api import GraphNode, GraphPayload

    with _DATASET_CACHE_LOCK:
        _DATASET_CACHE.clear()

    call_count = {"value": 0}

    def fake_loader(path):
        call_count["value"] += 1
        return GraphPayload(
            nodes=[GraphNode(id="company_dataset_cached", label="缓存企业", type="Company", properties={"name": "缓存企业"})],
            edges=[],
        )

    monkeypatch.setattr("app.main.load_financial_dataset_directory", fake_loader)

    first = client.post("/datasets/import", json={"dataset": "financial_datasets"})
    second = client.post("/datasets/import", json={"dataset": "financial_datasets"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert call_count["value"] == 1


def test_stock_analysis_cache_evicts_oldest_when_over_capacity(monkeypatch):
    monkeypatch.setattr("app.main.settings.stock_analysis_cache_max_size", 2)
    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: FailingGateway())

    from app.main import _stock_analysis_cache, _stock_analysis_cache_lock

    with _stock_analysis_cache_lock:
        _stock_analysis_cache.clear()

    for code in ("600000", "600001", "600002"):
        response = client.post(
            "/analysis/stock",
            json={"stock_code": code, "company_name": f"演示企业{code}"},
        )
        assert response.status_code == 200

    with _stock_analysis_cache_lock:
        cached_keys = list(_stock_analysis_cache.keys())

    assert len(cached_keys) == 2
    assert "600000" not in cached_keys
    assert cached_keys[-1] == "600002"


def test_cors_allow_origins_respect_settings_whitelist(monkeypatch):
    response = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "https://evil.example.com" not in response.headers.get("access-control-allow-origin", "")


def test_graph_path_returns_persisted_path_between_entities(monkeypatch):
    monkeypatch.setattr(
        "app.main.HttpLLMGateway",
        lambda: FakeGateway(
            '{"entities":[{"name":"路径公司","type":"Company","evidence":"路径公司完成A轮融资"},'
            '{"name":"路径资本","type":"Institution","evidence":"路径资本领投"},'
            '{"name":"A轮融资","type":"Event","evidence":"A轮融资"}],'
            '"relationships":[{"head":"路径资本","relation":"INVESTED_IN","tail":"A轮融资",'
            '"evidence":"路径资本领投路径公司A轮融资","confidence":0.91},'
            '{"head":"路径公司","relation":"RECEIVED_FUNDING","tail":"A轮融资",'
            '"evidence":"路径公司完成A轮融资","confidence":0.91}],'
            '"warnings":[]}'
        ),
    )

    extract_response = client.post(
        "/extract",
        json={
            "text": "路径公司完成A轮融资，路径资本领投。",
            "options": {"self_refine": False, "judge": False},
        },
    )
    assert extract_response.status_code == 200
    client.post("/graph/import", json=extract_response.json())

    response = client.get("/graph/path?source=路径资本&target=路径公司&max_depth=3")

    assert response.status_code == 200
    payload = response.json()
    assert payload["paths"]
    labels = {node["label"] for node in payload["paths"][0]["nodes"]}
    assert {"路径资本", "路径公司"}.issubset(labels)
