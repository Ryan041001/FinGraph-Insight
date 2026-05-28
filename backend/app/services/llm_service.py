from __future__ import annotations

import json
import time
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


LLM_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 Chrome/126 Safari/537.36"
)
RETRYABLE_LLM_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


def select_model_profile(task: LLMTask) -> ModelProfile:
    if task in {LLMTask.NEWS_SEARCH, LLMTask.MARKET_NEWS}:
        return ModelProfile(
            provider="default",
            model=settings.llm_model,
            purpose="实时消息面搜索与外部新闻补充",
            use_web_search=True,
        )

    if task in {LLMTask.GRAPH_RAG_STREAM, LLMTask.STOCK_ANALYSIS_STREAM}:
        return ModelProfile(
            provider="default",
            model=settings.llm_model,
            purpose="面向前端逐字展示的自然语言生成",
            use_json_output=False,
        )

    return ModelProfile(
        provider="default",
        model=settings.llm_model,
        purpose="金融结构化推理、抽取、裁判与图谱查询生成",
        use_json_output=True,
    )


def build_chat_payload(
    profile: ModelProfile,
    messages: list[dict[str, Any]],
    temperature: float = 0.2,
    top_p: float | None = 0.9,
    max_tokens: int | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": profile.model,
        "messages": messages,
        "temperature": temperature,
    }
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if presence_penalty is not None:
        payload["presence_penalty"] = presence_penalty
    if frequency_penalty is not None:
        payload["frequency_penalty"] = frequency_penalty
    if profile.use_json_output:
        payload["response_format"] = {"type": "json_object"}
    resolved_tools = tools
    if profile.use_web_search and resolved_tools is None:
        resolved_tools = [{"type": "web_search"}]
    if resolved_tools:
        payload["tools"] = resolved_tools
        payload["tool_choice"] = tool_choice if tool_choice is not None else "auto"
    return payload


class LLMGateway:
    def complete(
        self,
        *,
        task: LLMTask,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        top_p: float | None = 0.9,
        max_tokens: int | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    def stream_complete(
        self,
        *,
        task: LLMTask,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        top_p: float | None = 0.9,
        max_tokens: int | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ):
        yield self.complete(
            task=task,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            tools=tools,
            tool_choice=tool_choice,
        )


class HttpLLMGateway(LLMGateway):
    def complete(
        self,
        *,
        task: LLMTask,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        top_p: float | None = 0.9,
        max_tokens: int | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> str:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM calls.")
        if not settings.llm_model:
            raise RuntimeError("LLM_MODEL is required for LLM calls.")

        profile = select_model_profile(task)
        payload = build_chat_payload(
            profile,
            messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            tools=tools,
            tool_choice=tool_choice,
        )
        endpoint = f"{_base_url(profile.provider).rstrip('/')}/chat/completions"
        response = _post_chat_completion(endpoint, payload, timeout=_timeout_for_task(task))
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response missing choices.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if content is None:
            if message.get("tool_calls"):
                raise RuntimeError("LLM response returned tool_calls, but no tool dispatcher is configured.")
            raise RuntimeError("LLM response missing message content.")
        return str(content)

    def stream_complete(
        self,
        *,
        task: LLMTask,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        top_p: float | None = 0.9,
        max_tokens: int | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ):
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM calls.")
        if not settings.llm_model:
            raise RuntimeError("LLM_MODEL is required for LLM calls.")

        profile = select_model_profile(task)
        payload = build_chat_payload(
            profile,
            messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            tools=tools,
            tool_choice=tool_choice,
        )
        payload["stream"] = True
        endpoint = f"{_base_url(profile.provider).rstrip('/')}/chat/completions"
        attempts = max(1, int(settings.llm_max_retries) + 1)
        timeout = _timeout_for_task(task)
        for attempt_index in range(attempts):
            yielded_any = False
            try:
                with httpx.stream(
                    "POST",
                    endpoint,
                    headers=_llm_headers(),
                    json=payload,
                    timeout=timeout,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        data = line[6:].strip() if line.startswith("data: ") else line.strip()
                        if data == "[DONE]":
                            return
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
                            yielded_any = True
                            yield str(content)
                    return
            except Exception as exc:
                if yielded_any or attempt_index >= attempts - 1 or not _is_retryable_llm_error(exc):
                    raise
                backoff = max(0.0, float(settings.llm_retry_backoff_seconds)) * (2 ** attempt_index)
                if backoff:
                    time.sleep(backoff)


def _base_url(provider: str) -> str:
    if settings.openai_base_url:
        return settings.openai_base_url
    return "https://api.openai.com/v1"


def _llm_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "User-Agent": LLM_USER_AGENT,
        "Accept": "application/json",
    }


def _post_chat_completion(endpoint: str, payload: dict[str, Any], *, timeout: int | float) -> httpx.Response:
    attempts = max(1, int(settings.llm_max_retries) + 1)
    for attempt_index in range(attempts):
        try:
            response = httpx.post(
                endpoint,
                headers=_llm_headers(),
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            return response
        except Exception as exc:
            if attempt_index >= attempts - 1 or not _is_retryable_llm_error(exc):
                raise
            backoff = max(0.0, float(settings.llm_retry_backoff_seconds)) * (2 ** attempt_index)
            if backoff:
                time.sleep(backoff)
    raise RuntimeError("LLM retry loop exited unexpectedly.")


def _is_retryable_llm_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_LLM_STATUS_CODES
    return False


def _timeout_for_task(task: LLMTask) -> int:
    if task == LLMTask.TEXT2CYPHER:
        return settings.llm_text2cypher_timeout_seconds
    if task in {LLMTask.NEWS_SEARCH, LLMTask.MARKET_NEWS}:
        return settings.llm_news_timeout_seconds
    if task in {LLMTask.GRAPH_RAG_STREAM, LLMTask.STOCK_ANALYSIS_STREAM}:
        return settings.llm_stream_timeout_seconds
    return settings.llm_timeout_seconds
