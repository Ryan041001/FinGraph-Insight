from app.services.stock_analysis_service import build_stock_analysis


class FakeGateway:
    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        return '{"events":[{"event_type":"litigation","sentiment":"negative","title":"涉及诉讼","date":"2024-03-15","source_url":"https://example.com","evidence":"公告"}]}'


def test_build_stock_analysis_binds_graph_evidence_and_disclaimer():
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


def test_build_stock_analysis_can_refresh_news_with_grok_gateway():
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
