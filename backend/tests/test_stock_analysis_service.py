from app.models.api import GraphEdge, GraphNode, GraphPayload
from app.services.graph_store import graph_store
from app.services.stock_analysis_service import build_stock_analysis, build_stock_analysis_with_llm


class FakeGateway:
    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        return '{"events":[{"event_type":"litigation","sentiment":"negative","title":"涉及诉讼","date":"2024-03-15","source_url":"https://example.com","evidence":"公告"}]}'


class FakeAnalysisGateway:
    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        return '{"summary":"需要关注诉讼风险。","opportunity_factors":[],"risk_factors":[{"title":"诉讼风险","reason":"消息面出现诉讼","evidence_ids":["rel_1"],"severity":"medium"}],"graph_insights":[{"title":"图谱路径","path":"a->b","evidence_ids":["rel_1"]}],"confidence":0.81,"missing_data":[]}'


class IncompleteAnalysisGateway:
    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        return '{"summary":"模型只返回了摘要。"}'


def test_build_stock_analysis_binds_graph_evidence_and_disclaimer():
    graph_store.clear()
    graph_store.import_graph(
        GraphPayload(
            nodes=[
                GraphNode(id="company_spdb", label="浦发银行", type="Company", properties={"name": "浦发银行", "industry": "银行"}),
                GraphNode(id="event_spdb", label="浦发银行年度报告事件", type="Event", properties={"name": "浦发银行年度报告事件"}),
            ],
            edges=[
                GraphEdge(
                    id="rel_spdb_event",
                    source="company_spdb",
                    target="event_spdb",
                    type="MENTIONED_IN",
                    label="提及",
                    provenance={"source_text": "浦发银行披露年度报告。"},
                )
            ],
        )
    )

    response = build_stock_analysis(
        {
            "stock_code": "600000",
            "company_name": "浦发银行",
            "depth": 2,
            "news_window_days": 30,
        }
    )

    assert response["target"]["stock_code"] == "600000"
    assert response["target"]["company_name"] == "浦发银行"
    assert response["subgraph"]["nodes"]
    assert response["analysis"]["graph_insights"]
    assert response["analysis"]["disclaimer"] == "本结果仅用于课程项目演示和研究辅助，不构成投资建议。"
    assert all(
        insight.get("evidence_ids")
        for insight in response["analysis"]["graph_insights"]
    )


def test_build_stock_analysis_can_refresh_news_with_llm_gateway():
    graph_store.clear()
    response = build_stock_analysis(
        {
            "stock_code": "600000",
            "company_name": "浦发银行",
            "refresh_news": True,
        },
        news_gateway=FakeGateway(),
    )

    assert response["news_events"][0]["title"] == "涉及诉讼"
    assert response["news_events"][0]["source_url"] == "https://example.com"


def test_build_stock_analysis_merges_refreshed_news_into_runtime_graph():
    graph_store.clear()

    response = build_stock_analysis(
        {
            "stock_code": "",
            "company_name": "浦发银行",
            "refresh_news": True,
        },
        news_gateway=FakeGateway(),
    )

    edge_types = {edge["type"] for edge in response["subgraph"]["edges"]}
    labels = {node["label"] for node in response["subgraph"]["nodes"]}

    assert "浦发银行" in labels
    assert "涉及诉讼" in labels
    assert "MENTIONED_IN" in edge_types
    assert graph_store.subgraph("浦发银行").edges


def test_build_stock_analysis_with_llm_overrides_analysis_block():
    response = build_stock_analysis_with_llm(
        {"stock_code": "600000", "company_name": "浦发银行"},
        gateway=FakeAnalysisGateway(),
    )

    assert response["analysis"]["summary"] == "需要关注诉讼风险。"
    assert response["analysis"]["risk_factors"][0]["title"] == "诉讼风险"
    assert response["analysis"]["disclaimer"] == "本结果仅用于课程项目演示和研究辅助，不构成投资建议。"


def test_build_stock_analysis_with_llm_fills_missing_analysis_fields():
    response = build_stock_analysis_with_llm(
        {"stock_code": "600000", "company_name": "浦发银行"},
        gateway=IncompleteAnalysisGateway(),
    )

    assert response["analysis"]["summary"] == "模型只返回了摘要。"
    assert response["analysis"]["opportunity_factors"] == []
    assert response["analysis"]["risk_factors"] == []
    assert isinstance(response["analysis"]["graph_insights"], list)
    assert isinstance(response["analysis"]["missing_data"], list)
    assert response["analysis"]["disclaimer"] == "本结果仅用于课程项目演示和研究辅助，不构成投资建议。"
