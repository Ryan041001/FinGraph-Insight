from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.services.llm_service import LLMGateway, LLMTask
from app.services.graph_store import node_id
from app.services.entity_resolution_service import EntityResolver


entity_resolver = EntityResolver()


def extract_mock(text: str) -> dict:
    return extract_financial_text(text)


def extract_financial_text(text: str) -> dict:
    cleaned_text = re.sub(r"\s+", "", text or "")
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


def extract_with_deepseek(text: str, gateway: LLMGateway) -> dict:
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
    raw = json.loads(content)
    return _normalize_llm_extraction(text, raw)


def refine_extraction_with_deepseek(text: str, payload: dict[str, Any], gateway: LLMGateway) -> dict[str, Any]:
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
    raw = json.loads(content)
    return _normalize_llm_extraction(text, raw)


def judge_extraction_with_deepseek(payload: dict[str, Any], gateway: LLMGateway) -> dict[str, Any]:
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
    raw = json.loads(content)
    judgements = {
        str(item.get("temp_id")): item
        for item in raw.get("judgements", [])
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

    for index, entity in enumerate(raw.get("entities", []), start=1):
        name = str(entity.get("name", "")).strip()
        entity_type = str(entity.get("type", "Company")).strip()
        if not name:
            continue
        resolution = entity_resolver.resolve(name, entity_type)
        temp_id = f"e{index}"
        temp_by_name[name] = temp_id
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
    for index, relationship in enumerate(raw.get("relationships", []), start=1):
        confidence = float(relationship.get("confidence", 0.8))
        relationships.append(
            {
                "temp_id": f"r{index}",
                "head_temp_id": temp_by_name.get(str(relationship.get("head")), ""),
                "relation": relationship.get("relation", "RELATED_TO"),
                "tail_temp_id": temp_by_name.get(str(relationship.get("tail")), ""),
                "attributes": relationship.get("attributes", {}),
                "evidence": relationship.get("evidence", cleaned_text[:120]),
                "confidence": confidence,
                "status": _status_for_confidence(confidence),
            }
        )

    return {
        "document": {"title": None, "content_hash": content_hash},
        "entities": entities,
        "relationships": relationships,
        "warnings": raw.get("warnings", []),
    }


def _status_for_confidence(confidence: float) -> str:
    if confidence >= 0.8:
        return "confirmed"
    if confidence >= 0.5:
        return "pending_review"
    return "rejected"


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
