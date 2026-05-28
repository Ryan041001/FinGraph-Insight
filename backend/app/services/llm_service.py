from __future__ import annotations

import json
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
    GRAPH_RAG_STREAM = "graph_rag_stream"
    STOCK_ANALYSIS = "stock_analysis"
    STOCK_ANALYSIS_STREAM = "stock_analysis_stream"
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
            provider="default",
            model=settings.llm_model,
            purpose="实时消息面搜索与外部新闻补充",
            use_web_search=True,
            thinking=False,
        )

    if task in {LLMTask.GRAPH_RAG_STREAM, LLMTask.STOCK_ANALYSIS_STREAM}:
        return ModelProfile(
            provider="default",
            model=settings.llm_model,
            purpose="面向前端逐字展示的自然语言生成",
            use_json_output=False,
            thinking=True,
        )

    return ModelProfile(
        provider="default",
        model=settings.llm_model,
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

    def stream_complete(
        self,
        *,
        task: LLMTask,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ):
        yield self.complete(
            task=task,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )


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
        if not settings.llm_model:
            raise RuntimeError("LLM_MODEL is required for LLM calls.")

        profile = select_model_profile(task)
        payload = build_chat_payload(profile, messages, temperature=temperature, max_tokens=max_tokens)
        endpoint = f"{_base_url(profile.provider).rstrip('/')}/chat/completions"
        response = httpx.post(
            endpoint,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response missing choices.")
        content = (choices[0].get("message") or {}).get("content")
        if content is None:
            raise RuntimeError("LLM response missing message content.")
        return str(content)

    def stream_complete(
        self,
        *,
        task: LLMTask,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ):
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM calls.")
        if not settings.llm_model:
            raise RuntimeError("LLM_MODEL is required for LLM calls.")

        profile = select_model_profile(task)
        payload = build_chat_payload(profile, messages, temperature=temperature, max_tokens=max_tokens)
        payload["stream"] = True
        endpoint = f"{_base_url(profile.provider).rstrip('/')}/chat/completions"
        with httpx.stream(
            "POST",
            endpoint,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
            timeout=settings.llm_timeout_seconds,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = line[6:].strip() if line.startswith("data: ") else line.strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield str(content)


def _base_url(provider: str) -> str:
    if settings.openai_base_url:
        return settings.openai_base_url
    return "https://api.openai.com/v1"
