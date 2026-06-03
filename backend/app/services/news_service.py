from __future__ import annotations

from collections import OrderedDict
from threading import RLock
import time
from typing import Any

from app.config import settings
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

_NEWS_EVENT_CACHE: "OrderedDict[str, tuple[float, list[dict[str, Any]]]]" = OrderedDict()
_NEWS_EVENT_CACHE_LOCK = RLock()


def search_news_events(company_name: str, gateway: LLMGateway) -> list[dict[str, Any]]:
    cached_events = _get_cached_news_events(company_name)
    if cached_events is not None:
        return cached_events

    try:
        events = _search_news_events_with_prompt(
            company_name,
            gateway,
            task=LLMTask.NEWS_SEARCH,
            system_prompt=NEWS_JSON_SYSTEM_PROMPT,
            user_prompt=f"检索 {company_name} 最近30天重要金融新闻、公告、诉讼、处罚或融资事件。",
        )
        if events:
            _cache_news_events(company_name, events)
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
        resolved_events = events or [_default_public_clue_event(company_name)]
        if events:
            _cache_news_events(company_name, resolved_events)
        return resolved_events
    except Exception:
        return [_default_public_clue_event(company_name)]


def reset_news_event_cache() -> None:
    with _NEWS_EVENT_CACHE_LOCK:
        _NEWS_EVENT_CACHE.clear()


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


def _get_cached_news_events(company_name: str) -> list[dict[str, Any]] | None:
    cache_key = _news_cache_key(company_name)
    if not cache_key or settings.news_event_cache_ttl_seconds <= 0:
        return None

    now = time.time()
    with _NEWS_EVENT_CACHE_LOCK:
        cached = _NEWS_EVENT_CACHE.get(cache_key)
        if cached is None:
            return None
        created_at, events = cached
        if now - created_at > settings.news_event_cache_ttl_seconds:
            _NEWS_EVENT_CACHE.pop(cache_key, None)
            return None
        _NEWS_EVENT_CACHE.move_to_end(cache_key)
        return [dict(event) for event in events]


def _cache_news_events(company_name: str, events: list[dict[str, Any]]) -> None:
    cache_key = _news_cache_key(company_name)
    if not cache_key or settings.news_event_cache_ttl_seconds <= 0 or not events:
        return

    max_size = max(1, settings.news_event_cache_max_size)
    with _NEWS_EVENT_CACHE_LOCK:
        _NEWS_EVENT_CACHE[cache_key] = (time.time(), [dict(event) for event in events])
        _NEWS_EVENT_CACHE.move_to_end(cache_key)
        while len(_NEWS_EVENT_CACHE) > max_size:
            _NEWS_EVENT_CACHE.popitem(last=False)


def _news_cache_key(company_name: str) -> str:
    return " ".join(str(company_name or "").strip().lower().split())
