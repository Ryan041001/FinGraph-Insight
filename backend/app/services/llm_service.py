from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx

from app.config import settings


class LLMTask(StrEnum):
    EXTRACTION = "extraction"
    JUDGE = "judge"
    TEXT2CYPHER = "text2cypher"
    GRAPH_RAG = "graph_rag"
    STOCK_ANALYSIS = "stock_analysis"
    NEWS_SEARCH = "news_search"
    MARKET_NEWS = "market_news"


@dataclass(frozen=True)
class ModelProfile:
    provider: str
    model: str
    purpose: str
    use_json_output: bool = False
    use_web_search: bool = False
    thinking: bool = False


def select_model_profile(task: LLMTask) -> ModelProfile:
    if task in {LLMTask.NEWS_SEARCH, LLMTask.MARKET_NEWS}:
        return ModelProfile(
            provider="grok",
            model=settings.llm_model_grok,
            purpose="实时消息面搜索与外部新闻补充",
            use_web_search=True,
            thinking=False,
        )

    return ModelProfile(
        provider="deepseek",
        model=settings.llm_model_deepseek,
        purpose="金融结构化推理、抽取、裁判与图谱查询生成",
        use_json_output=True,
        thinking=True,
    )


def build_chat_payload(
    profile: ModelProfile,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": profile.model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if profile.use_json_output:
        payload["response_format"] = {"type": "json_object"}
    if profile.use_web_search:
        payload["tools"] = [{"type": "web_search"}]
    if profile.thinking:
        payload["thinking"] = {"type": "enabled"}
    return payload


class LLMGateway:
    def complete(
        self,
        *,
        task: LLMTask,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        raise NotImplementedError


class HttpLLMGateway(LLMGateway):
    def complete(
        self,
        *,
        task: LLMTask,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM calls.")

        profile = select_model_profile(task)
        payload = build_chat_payload(profile, messages, temperature=temperature, max_tokens=max_tokens)
        endpoint = f"{_base_url(profile.provider).rstrip('/')}/chat/completions"
        response = httpx.post(
            endpoint,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _base_url(provider: str) -> str:
    if settings.openai_base_url:
        return settings.openai_base_url
    if provider == "grok":
        return "https://api.x.ai/v1"
    return "https://api.deepseek.com"
