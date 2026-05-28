from app.services.stock_analysis_service import build_stock_analysis


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
