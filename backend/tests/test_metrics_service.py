import json

from app.services.metrics_service import evaluate_gold_standard


def test_evaluate_gold_standard_scores_predictions_against_gold(tmp_path):
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(
        json.dumps(
            [
                {
                    "id": "gold_001",
                    "text": "星河数据完成B轮融资，红杉资本领投。",
                    "entities": [
                        {"name": "星河数据", "type": "Company"},
                        {"name": "红杉资本", "type": "Institution"},
                    ],
                    "relationships": [
                        {"head": "红杉资本", "relation": "INVESTED_IN", "tail": "星河数据"}
                    ],
                },
                {
                    "id": "gold_002",
                    "text": "蓝海智能完成A轮融资，启明创投参与投资。",
                    "entities": [
                        {"name": "蓝海智能", "type": "Company"},
                        {"name": "启明创投", "type": "Institution"},
                    ],
                    "relationships": [
                        {"head": "启明创投", "relation": "INVESTED_IN", "tail": "蓝海智能"}
                    ],
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def predictor(text):
        if "星河数据" in text:
            return {
                "entities": [
                    {"name": "星河数据", "type": "Company"},
                    {"name": "红杉资本", "type": "Institution"},
                ],
                "relationships": [
                    {
                        "head": "红杉资本",
                        "relation": "INVESTED_IN",
                        "tail": "星河数据",
                        "confidence": 0.94,
                        "status": "confirmed",
                    }
                ],
            }
        return {
            "entities": [
                {"name": "蓝海智能", "type": "Company"},
                {"name": "幻觉资本", "type": "Institution"},
            ],
            "relationships": [
                {
                    "head": "幻觉资本",
                    "relation": "INVESTED_IN",
                    "tail": "蓝海智能",
                    "confidence": 0.91,
                    "status": "confirmed",
                }
            ],
        }

    metrics = evaluate_gold_standard(gold_path, predictor=predictor)

    assert metrics["sample_count"] == 2
    assert metrics["entity_precision"] == 0.75
    assert metrics["entity_recall"] == 0.75
    assert metrics["entity_f1"] == 0.75
    assert metrics["relation_precision"] == 0.5
    assert metrics["relation_recall"] == 0.5
    assert metrics["relation_f1"] == 0.5
    assert metrics["hallucination_rate"] == 0.5
    assert metrics["effective_import_rate"] == 1.0
    assert len(metrics["per_sample"]) == 2
