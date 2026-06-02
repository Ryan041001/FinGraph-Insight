from __future__ import annotations

from typing import Any

from app.services.llm_service import LLMGateway, LLMTask
from app.services.llm_json import parse_llm_json_object, require_llm_json_list


NEWS_JSON_SYSTEM_PROMPT = (
    "你是金融消息面检索助手。请使用实时搜索能力查找公司近期新闻，"
    "并严格输出 json：{\"events\":[{\"event_type\":\"...\",\"sentiment\":\"positive|neutral|negative|unknown\","
    "\"title\":\"...\",\"date\":\"YYYY-MM-DD\",\"source_url\":\"...\",\"evidence\":\"...\"}]}。"
    "不得输出买卖建议。"
)


NEWS_FALLBACK_SYSTEM_PROMPT = (
    "你是金融企业公开线索整理助手。外部实时搜索工具暂不可用时，"
    "请基于你可用的公开知识和用户给定企业名，输出可进一步核验的公司线索。"
    "严格输出 json：{\"events\":[{\"event_type\":\"company_profile|product|financing|risk|public_info\","
    "\"sentiment\":\"positive|neutral|negative|unknown\",\"title\":\"...\",\"date\":\"未知\","
    "\"source_url\":\"\",\"evidence\":\"...\"}]}。"
    "如果不了解该企业，也要返回一条 title 为 企业线索待核验 的 unknown 事件，提示需要继续核验；不得输出买卖建议。"
)


def search_news_events(company_name: str, gateway: LLMGateway) -> list[dict[str, Any]]:
    try:
        events = _search_news_events_with_prompt(
            company_name,
            gateway,
            task=LLMTask.NEWS_SEARCH,
            system_prompt=NEWS_JSON_SYSTEM_PROMPT,
            user_prompt=f"检索 {company_name} 最近30天重要金融新闻、公告、诉讼、处罚或融资事件。",
        )
        if events:
            return events
    except Exception:
        pass

    try:
        events = _search_news_events_with_prompt(
            company_name,
            gateway,
            task=LLMTask.STOCK_ANALYSIS,
            system_prompt=NEWS_FALLBACK_SYSTEM_PROMPT,
            user_prompt=f"整理 {company_name} 的公开公司线索、产品业务、融资或风险事件；仅输出 JSON。",
        )
        return events or [_default_public_clue_event(company_name)]
    except Exception:
        return [_default_public_clue_event(company_name)]


def _search_news_events_with_prompt(
    company_name: str,
    gateway: LLMGateway,
    *,
    task: LLMTask,
    system_prompt: str,
    user_prompt: str,
) -> list[dict[str, Any]]:
    content = gateway.complete(
        task=task,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=2048,
    )
    payload = parse_llm_json_object(content)
    events = require_llm_json_list(payload, "events")
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("LLM output field 'events' must contain objects.")
        event.setdefault("source_url", "")
        event.setdefault("date", "未知")
        event.setdefault("sentiment", "unknown")
        event.setdefault("event_type", "public_info")
    return events


def _default_public_clue_event(company_name: str) -> dict[str, str]:
    return {
        "event_type": "public_info",
        "sentiment": "unknown",
        "title": "企业线索待核验",
        "date": "未知",
        "source_url": "",
        "evidence": f"{company_name} 暂未获取到可直接核验的证据线索，已保留企业名称并等待后续补充。",
    }
