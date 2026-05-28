from pathlib import Path

from app.services.graph_rag_service import answer_with_graph_context
from app.services.metrics_service import evaluate_gold_standard
from app.services.extraction_service import extract_financial_text
from tests.graph_fixtures import funding_graph


def test_graph_rag_answer_uses_supporting_graph_evidence():
    graph = funding_graph("星河数据")

    response = answer_with_graph_context("星河数据有哪些融资关系？", graph)

    assert "星河数据" in response["answer"]
    assert response["supporting_graph"]["nodes"]
    assert response["citations"]
    assert response["citations"][0]["source_text"]


def test_evaluate_gold_standard_returns_metric_contract():
    gold_path = Path(__file__).resolve().parents[2] / "data" / "gold" / "gold_standard.json"

    metrics = evaluate_gold_standard(gold_path, predictor=extract_financial_text)

    assert metrics["sample_count"] >= 50
    assert 0.0 <= metrics["entity_precision"] <= 1.0
    assert 0.0 <= metrics["entity_recall"] <= 1.0
    assert 0.0 <= metrics["relation_precision"] <= 1.0
    assert 0.0 <= metrics["relation_recall"] <= 1.0
    assert 0.0 <= metrics["hallucination_rate"] <= 1.0
    assert metrics["per_sample"]
