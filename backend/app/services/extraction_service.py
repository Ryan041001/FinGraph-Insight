from __future__ import annotations

import hashlib
import re

from app.services.graph_store import node_id


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
