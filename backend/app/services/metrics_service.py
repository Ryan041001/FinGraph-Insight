from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Callable
from typing import Any

from app.services.entity_resolution_service import normalize_entity_name


PredictionFunction = Callable[[str], dict[str, Any]]


def evaluate_gold_standard(
    path: str | Path,
    predictor: PredictionFunction | None = None,
) -> dict[str, Any]:
    if predictor is None:
        raise RuntimeError("A real extraction predictor must be configured for metrics evaluation.")

    samples = json.loads(Path(path).read_text(encoding="utf-8"))
    entity_gold_total = 0
    entity_pred_total = 0
    entity_correct_total = 0
    relation_gold_total = 0
    relation_pred_total = 0
    relation_correct_total = 0
    confirmed_relation_total = 0
    per_sample: list[dict[str, Any]] = []

    for sample in samples:
        gold_entities = _entity_keys(sample)
        gold_relationships = _relationship_keys(sample)
        try:
            prediction = predictor(str(sample.get("text", "")))
            error = None
        except Exception as exc:
            prediction = {"entities": [], "relationships": []}
            error = str(exc)

        predicted_entities = _entity_keys(prediction)
        predicted_relationships = _relationship_keys(prediction)
        confirmed_relationships = _confirmed_relationship_count(prediction)

        entity_correct = len(gold_entities & predicted_entities)
        relation_correct = len(gold_relationships & predicted_relationships)

        entity_gold_total += len(gold_entities)
        entity_pred_total += len(predicted_entities)
        entity_correct_total += entity_correct
        relation_gold_total += len(gold_relationships)
        relation_pred_total += len(predicted_relationships)
        relation_correct_total += relation_correct
        confirmed_relation_total += confirmed_relationships

        per_sample.append(
            {
                "id": sample.get("id"),
                "entity_gold": len(gold_entities),
                "entity_predicted": len(predicted_entities),
                "entity_correct": entity_correct,
                "relation_gold": len(gold_relationships),
                "relation_predicted": len(predicted_relationships),
                "relation_correct": relation_correct,
                "error": error,
            }
        )

    entity_precision = _safe_ratio(entity_correct_total, entity_pred_total)
    entity_recall = _safe_ratio(entity_correct_total, entity_gold_total)
    relation_precision = _safe_ratio(relation_correct_total, relation_pred_total)
    relation_recall = _safe_ratio(relation_correct_total, relation_gold_total)
    false_relationships = max(0, relation_pred_total - relation_correct_total)

    return {
        "sample_count": len(samples),
        "entity_precision": entity_precision,
        "entity_recall": entity_recall,
        "entity_f1": _f1(entity_precision, entity_recall),
        "relation_precision": relation_precision,
        "relation_recall": relation_recall,
        "relation_f1": _f1(relation_precision, relation_recall),
        "hallucination_rate": _safe_ratio(false_relationships, relation_pred_total),
        "effective_import_rate": _safe_ratio(confirmed_relation_total, relation_pred_total),
        "per_sample": per_sample,
    }


def default_gold_standard_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "gold" / "gold_standard.json"


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _entity_keys(payload: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (
            normalize_entity_name(str(entity.get("resolved_name") or entity.get("name", ""))),
            str(entity.get("type", "Entity")),
        )
        for entity in payload.get("entities", [])
        if str(entity.get("resolved_name") or entity.get("name", "")).strip()
    }


def _relationship_keys(payload: dict[str, Any]) -> set[tuple[str, str, str]]:
    temp_to_name = {
        str(entity.get("temp_id")): str(entity.get("resolved_name") or entity.get("name", ""))
        for entity in payload.get("entities", [])
        if entity.get("temp_id")
    }
    keys: set[tuple[str, str, str]] = set()
    for relationship in payload.get("relationships", []):
        head = relationship.get("head") or temp_to_name.get(str(relationship.get("head_temp_id")), "")
        tail = relationship.get("tail") or temp_to_name.get(str(relationship.get("tail_temp_id")), "")
        relation = str(relationship.get("relation", "RELATED_TO"))
        if not head or not tail:
            continue
        keys.add((normalize_entity_name(str(head)), relation, normalize_entity_name(str(tail))))
    return keys


def _confirmed_relationship_count(payload: dict[str, Any]) -> int:
    count = 0
    for relationship in payload.get("relationships", []):
        status = str(relationship.get("status", ""))
        confidence = float(relationship.get("confidence", 0))
        if status == "confirmed" or (status != "rejected" and confidence >= 0.8):
            count += 1
    return count
