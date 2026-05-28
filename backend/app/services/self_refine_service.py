from __future__ import annotations

import json
from typing import Any

from app.services.extraction_service import _normalize_llm_extraction, extract_with_llm
from app.services.llm_service import LLMGateway, LLMTask


def extract_with_self_refine(
    text: str,
    gateway: LLMGateway,
    max_iterations: int = 2,
) -> dict[str, Any]:
    payload = extract_with_llm(text, gateway)
    for _ in range(max(0, max_iterations)):
        critique = critique_extraction(text, payload, gateway)
        if not critique.get("issues"):
            break
        payload = refine_from_critique(text, payload, critique, gateway)
    return payload


def critique_extraction(text: str, payload: dict[str, Any], gateway: LLMGateway) -> dict[str, Any]:
    content = gateway.complete(
        task=LLMTask.EXTRACTION,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是金融知识图谱抽取质量检查员。请只基于原文检查抽取结果，"
                    "识别遗漏实体、实体类型错误、关系方向错误、原文不支持的关系、证据不足。"
                    "严格输出 json：{\"issues\":[{\"type\":\"...\",\"description\":\"...\"}]}。"
                    "如果没有问题，输出 {\"issues\":[]}。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"text": text, "extraction": payload},
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0,
        max_tokens=1024,
    )
    critique = json.loads(content)
    if not isinstance(critique, dict):
        return {"issues": [{"type": "invalid_critique", "description": "critique result is not an object"}]}
    issues = critique.get("issues", [])
    if not isinstance(issues, list):
        return {"issues": [{"type": "invalid_critique", "description": "issues is not a list"}]}
    return {"issues": issues}


def refine_from_critique(
    text: str,
    payload: dict[str, Any],
    critique: dict[str, Any],
    gateway: LLMGateway,
) -> dict[str, Any]:
    content = gateway.complete(
        task=LLMTask.EXTRACTION,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是金融知识图谱抽取修正器。请根据批评意见修正抽取结果，"
                    "删除原文不支持的关系，补充明确支持的实体和关系。"
                    "严格输出 json，包含 entities、relationships、warnings。"
                    "实体类型只允许 Company、Person、Institution、Event、Industry。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "text": text,
                        "current_extraction": payload,
                        "critique": critique,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0,
        max_tokens=2048,
    )
    raw = json.loads(content)
    return _normalize_llm_extraction(text, raw)
