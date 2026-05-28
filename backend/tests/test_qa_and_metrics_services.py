from pathlib import Path

from app.services.graph_rag_service import answer_with_graph_context
from app.services.metrics_service import evaluate_gold_standard
from app.services.mock_data import sample_graph


def test_graph_rag_answer_uses_supporting_graph_evidence():
    graph = sample_graph("示例科技")

    response = answer_with_graph_context("示例科技有哪些融资关系？", graph)

    assert "示例科技" in response["answer"]
    assert response["supporting_graph"]["nodes"]
    assert response["citations"]
    assert response["citations"][0]["source_text"]


def test_evaluate_gold_standard_returns_metric_contract():
    gold_path = Path(__file__).resolve().parents[2] / "data" / "gold" / "gold_standard.json"

    metrics = evaluate_gold_standard(gold_path)

    assert metrics["sample_count"] == 1
    assert metrics["entity_precision"] == 1.0
    assert metrics["entity_recall"] == 1.0
    assert metrics["relation_precision"] == 1.0
    assert metrics["relation_recall"] == 1.0
    assert metrics["hallucination_rate"] == 0.0
