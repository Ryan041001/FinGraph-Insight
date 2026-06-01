from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.services.llm_service import LLMGateway, LLMTask
from app.services.llm_json import parse_llm_json_object, require_llm_json_list
from app.services.graph_store import node_id
from app.services.entity_resolution_service import EntityResolver


entity_resolver = EntityResolver()


def extract_financial_text(text: str) -> dict:
    cleaned_text = re.sub(r"\s+", "", text or "")
    rule_payload = _extract_financing_rule(cleaned_text)
    if rule_payload is not None:
        return rule_payload

    company_name, round_name = _extract_company_and_round(cleaned_text)
    investor_name = _extract_investor(cleaned_text)
    event_name = f"{company_name}{round_name}融资事件"
    content_hash = hashlib.sha1(cleaned_text.encode("utf-8")).hexdigest()[:16]

    return {
        "document": {
            "title": None,
            "content_hash": content_hash,
        },
        "entities": [
            {
                "temp_id": "e1",
                "name": investor_name,
                "type": "Institution",
                "resolved_id": node_id("Institution", investor_name),
                "resolution_confidence": 0.94,
                "evidence": investor_name,
            },
            {
                "temp_id": "e2",
                "name": company_name,
                "type": "Company",
                "resolved_id": node_id("Company", company_name),
                "resolution_confidence": 0.9,
                "evidence": company_name,
            },
            {
                "temp_id": "e3",
                "name": event_name,
                "type": "Event",
                "resolved_id": node_id("Event", event_name),
                "resolution_confidence": 0.86,
                "evidence": f"{round_name}融资",
            },
        ],
        "relationships": [
            {
                "temp_id": "r1",
                "head_temp_id": "e1",
                "relation": "INVESTED_IN",
                "tail_temp_id": "e3",
                "attributes": {"role": _extract_role(cleaned_text), "round": round_name},
                "evidence": cleaned_text[:120],
                "confidence": 0.91,
                "status": "confirmed",
            },
            {
                "temp_id": "r2",
                "head_temp_id": "e2",
                "relation": "RECEIVED_FUNDING",
                "tail_temp_id": "e3",
                "attributes": {"round": round_name},
                "evidence": cleaned_text[:120],
                "confidence": 0.91,
                "status": "confirmed",
            },
        ],
        "warnings": [],
    }


def extract_with_llm(text: str, gateway: LLMGateway) -> dict:
    content = gateway.complete(
        task=LLMTask.EXTRACTION,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是金融知识图谱抽取器。请严格输出 json，包含 entities、relationships、warnings。"
                    "实体类型只允许 Company、Person、Institution、Event、Industry。"
                    "关系类型优先使用 INVESTED_IN、RECEIVED_FUNDING、HOLDS_SHARES、LEGAL_REP_OF、EXECUTIVE_OF。"
                ),
            },
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=2048,
    )
    raw = parse_llm_json_object(content)
    return _apply_rule_fallback(text, _normalize_llm_extraction(text, raw))


def refine_extraction_with_llm(text: str, payload: dict[str, Any], gateway: LLMGateway) -> dict[str, Any]:
    content = gateway.complete(
        task=LLMTask.EXTRACTION,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是金融知识图谱抽取结果审查器。请根据原文修正遗漏、实体类型错误、关系方向错误和幻觉关系。"
                    "严格输出 json，包含 entities、relationships、warnings。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"text": text, "current_extraction": payload},
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0,
        max_tokens=2048,
    )
    raw = parse_llm_json_object(content)
    return _apply_rule_fallback(text, _normalize_llm_extraction(text, raw))


def judge_extraction_with_llm(payload: dict[str, Any], gateway: LLMGateway) -> dict[str, Any]:
    content = gateway.complete(
        task=LLMTask.JUDGE,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是金融关系抽取裁判。请严格输出 json，格式为 "
                    "{\"judgements\":[{\"temp_id\":\"r1\",\"confidence\":0.9,\"reason\":\"...\"}]}。"
                    "confidence 规则：1.0 原文明确支持，0.8 强支持，0.5 不确定，0.2 依据弱，0.0 不支持。"
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0,
        max_tokens=1024,
    )
    raw = parse_llm_json_object(content)
    judgements = {
        str(item.get("temp_id")): item
        for item in require_llm_json_list(raw, "judgements")
        if isinstance(item, dict)
    }
    judged = {
        **payload,
        "relationships": [dict(relationship) for relationship in payload.get("relationships", [])],
    }

    for relationship in judged["relationships"]:
        judgement = judgements.get(str(relationship.get("temp_id")))
        if not judgement:
            continue
        confidence = float(judgement.get("confidence", relationship.get("confidence", 0.5)))
        relationship["confidence"] = confidence
        relationship["status"] = _status_for_confidence(confidence)
        relationship["judge_reason"] = judgement.get("reason", "")

    return judged


def _normalize_llm_extraction(text: str, raw: dict[str, Any]) -> dict:
    cleaned_text = re.sub(r"\s+", "", text or "")
    content_hash = hashlib.sha1(cleaned_text.encode("utf-8")).hexdigest()[:16]
    temp_by_name: dict[str, str] = {}
    entities: list[dict[str, Any]] = []
    raw_entities = require_llm_json_list(raw, "entities")

    for index, entity in enumerate(raw_entities, start=1):
        if not isinstance(entity, dict):
            raise ValueError("LLM output field 'entities' must contain objects.")
        name = str(entity.get("name", "")).strip()
        entity_type = str(entity.get("type", "Company")).strip()
        if not name:
            continue
        resolution = entity_resolver.resolve(name, entity_type)
        temp_id = f"e{index}"
        # First occurrence wins: a later duplicate name must not steal an earlier
        # entity's temp_id (which would silently rewire relationships).
        temp_by_name.setdefault(name, temp_id)
        entities.append(
            {
                "temp_id": temp_id,
                "name": name,
                "type": entity_type,
                "resolved_id": resolution["resolved_id"],
                "resolved_name": resolution["resolved_name"],
                "normalized_name": resolution["normalized_name"],
                "resolution_match_type": resolution["match_type"],
                "resolution_candidates": resolution.get("candidates", []),
                "resolution_confidence": float(
                    entity.get("resolution_confidence", resolution["confidence"])
                ),
                "evidence": entity.get("evidence", name),
            }
        )

    relationships: list[dict[str, Any]] = []
    dropped_relationships: list[dict[str, Any]] = []
    raw_relationships = require_llm_json_list(raw, "relationships")
    for index, relationship in enumerate(raw_relationships, start=1):
        if not isinstance(relationship, dict):
            raise ValueError("LLM output field 'relationships' must contain objects.")
        head_name = _relationship_endpoint_name(relationship, "head")
        tail_name = _relationship_endpoint_name(relationship, "tail")
        head_temp_id = temp_by_name.get(head_name, "")
        tail_temp_id = temp_by_name.get(tail_name, "")
        # Don't emit dangling edges: if either endpoint can't be matched to an
        # extracted entity, record it as a warning and skip instead of producing
        # a relationship with an empty head/tail that gets silently dropped on import.
        if not head_temp_id or not tail_temp_id:
            dropped_relationships.append(
                {
                    "relation": relationship.get("relation", "RELATED_TO"),
                    "head": relationship.get("head"),
                    "tail": relationship.get("tail"),
                    "reason": "endpoint not found among extracted entities",
                }
            )
            continue
        confidence = float(relationship.get("confidence", 0.8))
        relationships.append(
            {
                "temp_id": f"r{index}",
                "head_temp_id": head_temp_id,
                "relation": _relationship_type(relationship),
                "tail_temp_id": tail_temp_id,
                "attributes": relationship.get("attributes", {}),
                "evidence": relationship.get("evidence", cleaned_text[:120]),
                "confidence": confidence,
                "status": _status_for_confidence(confidence),
            }
        )

    warnings = raw.get("warnings", [])
    if not isinstance(warnings, list):
        raise ValueError("LLM output field 'warnings' must be a list.")
    warnings = list(warnings)
    for dropped in dropped_relationships:
        warnings.append(
            f"关系 {dropped['head']} -[{dropped['relation']}]-> {dropped['tail']} 的端点未在抽取实体中找到，已跳过。"
        )

    return {
        "document": {"title": None, "content_hash": content_hash},
        "entities": entities,
        "relationships": relationships,
        "warnings": warnings,
    }


def _status_for_confidence(confidence: float) -> str:
    if confidence >= 0.8:
        return "confirmed"
    if confidence >= 0.5:
        return "pending_review"
    return "rejected"


def _relationship_endpoint_name(relationship: dict[str, Any], side: str) -> str:
    if side == "head":
        candidates = ("head", "source", "from", "subject", "head_entity", "source_entity")
    else:
        candidates = ("tail", "target", "to", "object", "tail_entity", "target_entity")

    for key in candidates:
        value = relationship.get(key)
        if isinstance(value, dict):
            value = value.get("name") or value.get("label") or value.get("text")
        if value is not None:
            name = str(value).strip()
            if name:
                return name
    return ""


def _relationship_type(relationship: dict[str, Any]) -> str:
    aliases = {
        "投资": "INVESTED_IN",
        "领投": "INVESTED_IN",
        "跟投": "INVESTED_IN",
        "参与投资": "INVESTED_IN",
        "融资": "RECEIVED_FUNDING",
        "获得融资": "RECEIVED_FUNDING",
        "完成融资": "RECEIVED_FUNDING",
        "持股": "HOLDS_SHARES",
        "法人": "LEGAL_REP_OF",
        "任职": "EXECUTIVE_OF",
    }
    for key in ("relation", "type", "relationship", "predicate", "label"):
        value = relationship.get(key)
        if value is None:
            continue
        relation = str(value).strip()
        if relation:
            return aliases.get(relation, relation.upper())
    return "RELATED_TO"


def _apply_rule_fallback(text: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("relationships"):
        return payload
    fallback = extract_financial_text(text)
    fallback_names = {str(entity.get("name", "")) for entity in fallback.get("entities", [])}
    if "当前企业" in fallback_names or "未知投资方" in fallback_names:
        return payload
    return {
        **fallback,
        "warnings": [
            *payload.get("warnings", []),
            "LLM 未抽出完整融资关系，已使用本地融资规则补全实体和关系。",
        ],
    }


def _extract_financing_rule(text: str) -> dict[str, Any] | None:
    match = re.search(
        r"(?:^|[，,。；;])(?P<company>[\u4e00-\u9fa5A-Za-z0-9（）()·]+?)完成(?P<round>[A-Za-z0-9+\-]*轮|天使轮|种子轮)融资",
        text,
    )
    if not match:
        return None

    company_name = match.group("company")
    round_name = match.group("round")
    investors = _extract_investors(text)
    if not company_name or not investors:
        return None

    event_name = f"{company_name}{round_name}融资事件"
    content_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []

    for index, (investor_name, role) in enumerate(investors, start=1):
        investor_temp_id = f"e_investor_{index}"
        entities.append(
            {
                "temp_id": investor_temp_id,
                "name": investor_name,
                "type": "Institution",
                "resolved_id": node_id("Institution", investor_name),
                "resolution_confidence": 0.94,
                "evidence": investor_name,
            }
        )
        relationships.append(
            {
                "temp_id": f"r_investor_{index}",
                "head_temp_id": investor_temp_id,
                "relation": "INVESTED_IN",
                "tail_temp_id": "e_event",
                "attributes": {"role": role, "round": round_name},
                "evidence": text[:120],
                "confidence": 0.91,
                "status": "confirmed",
            }
        )

    entities.extend(
        [
            {
                "temp_id": "e_company",
                "name": company_name,
                "type": "Company",
                "resolved_id": node_id("Company", company_name),
                "resolution_confidence": 0.9,
                "evidence": company_name,
            },
            {
                "temp_id": "e_event",
                "name": event_name,
                "type": "Event",
                "resolved_id": node_id("Event", event_name),
                "resolution_confidence": 0.86,
                "evidence": f"{round_name}融资",
            },
        ]
    )
    relationships.append(
        {
            "temp_id": "r_company_funding",
            "head_temp_id": "e_company",
            "relation": "RECEIVED_FUNDING",
            "tail_temp_id": "e_event",
            "attributes": {"round": round_name},
            "evidence": text[:120],
            "confidence": 0.91,
            "status": "confirmed",
        }
    )

    return {
        "document": {"title": None, "content_hash": content_hash},
        "entities": entities,
        "relationships": relationships,
        "warnings": [],
    }


def _extract_investors(text: str) -> list[tuple[str, str]]:
    investors: list[tuple[str, str]] = []
    for match in re.finditer(
        r"(?:由|，|,|；|;|、)?(?P<investor>[\u4e00-\u9fa5A-Za-z0-9（）()·]+?)(?P<role>领投|跟投|参与投资|投资)",
        text,
    ):
        investor = match.group("investor").strip("由，,；;、。")
        role = match.group("role")
        if investor and investor not in {"融资金额"}:
            investors.append((investor, role))
    return investors


def _extract_company_and_round(text: str) -> tuple[str, str]:
    match = re.search(r"(?P<company>[\u4e00-\u9fa5A-Za-z0-9（）()·]+?)完成(?P<round>[A-Za-z0-9+\-]*轮|天使轮|种子轮)融资", text)
    if match:
        return match.group("company"), match.group("round")

    colon_match = re.search(r"当前企业[:：](?P<company>[\u4e00-\u9fa5A-Za-z0-9（）()·]+)", text)
    if colon_match:
        return colon_match.group("company"), "B轮"

    return "当前企业", "B轮"


def _extract_investor(text: str) -> str:
    role_match = re.search(r"[，,。；;](?P<investor>[\u4e00-\u9fa5A-Za-z0-9（）()·]+?)(?:领投|参与投资|跟投|投资)", text)
    if role_match:
        return role_match.group("investor")

    leading_match = re.search(r"(?P<investor>[\u4e00-\u9fa5A-Za-z0-9（）()·]+?)(?:领投|参与投资|跟投|投资)", text)
    if leading_match:
        return leading_match.group("investor")

    return "未知投资方"


def _extract_role(text: str) -> str:
    if "领投" in text:
        return "领投"
    if "跟投" in text:
        return "跟投"
    if "参与投资" in text:
        return "参与投资"
    return "投资"
