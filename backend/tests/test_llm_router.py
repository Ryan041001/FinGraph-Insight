import json

import httpx
import pytest

from app.services.llm_service import (
    HttpLLMGateway,
    LLMTask,
    ModelProfile,
    build_chat_payload,
    select_model_profile,
)
from app.config import Settings, settings


MODEL_NAME = __name__.replace(".", "-")


def test_settings_enable_llm_by_default_without_env_toggle(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")

    settings = Settings(_env_file=env_path)

    assert settings.llm_enabled is True


def test_settings_exposes_single_model_and_timeout_config(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=shared-key",
                "OPENAI_BASE_URL=https://llm-gateway.example/v1",
                f"LLM_MODEL={MODEL_NAME}",
                "LLM_TIMEOUT_SECONDS=120",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_path)

    assert settings.openai_base_url == "https://llm-gateway.example/v1"
    assert settings.llm_model == MODEL_NAME
    assert settings.llm_timeout_seconds == 120


def test_settings_exposes_optional_llm_fallback_routes(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=shared-key",
                f"LLM_MODEL={MODEL_NAME}",
                "LLM_FALLBACK_MODELS=fallback-mini, fallback-large",
                "OPENAI_FALLBACK_BASE_URLS=https://backup-one.example/v1, https://backup-two.example/v1",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_path)

    assert settings.llm_fallback_models == "fallback-mini, fallback-large"
    assert settings.openai_fallback_base_urls == "https://backup-one.example/v1, https://backup-two.example/v1"


def test_select_model_profile_uses_single_model_for_structured_tasks(monkeypatch):
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", MODEL_NAME)

    profile = select_model_profile(LLMTask.EXTRACTION)

    assert profile.provider == "default"
    assert profile.model == settings.llm_model
    assert profile.use_json_output is True

    assert select_model_profile(LLMTask.JUDGE).provider == "default"
    assert select_model_profile(LLMTask.TEXT2CYPHER).provider == "default"
    assert select_model_profile(LLMTask.STOCK_ANALYSIS).provider == "default"


def test_select_model_profile_uses_single_model_with_web_search_for_news_tasks(monkeypatch):
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", MODEL_NAME)

    profile = select_model_profile(LLMTask.NEWS_SEARCH)

    assert profile.provider == "default"
    assert profile.model == settings.llm_model
    assert profile.use_web_search is True
    assert select_model_profile(LLMTask.MARKET_NEWS).provider == "default"


def test_build_chat_payload_uses_json_response_format_for_structured_tasks():
    profile = ModelProfile(
        provider="default",
        model=MODEL_NAME,
        purpose="金融结构化抽取",
        use_json_output=True,
    )

    payload = build_chat_payload(
        profile=profile,
        messages=[{"role": "user", "content": "抽取实体关系"}],
        temperature=0,
    )

    assert payload["model"] == MODEL_NAME
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0


def test_build_chat_payload_does_not_send_provider_specific_thinking_param(monkeypatch):
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", MODEL_NAME)
    profile = select_model_profile(LLMTask.EXTRACTION)

    payload = build_chat_payload(
        profile=profile,
        messages=[{"role": "user", "content": "抽取实体关系"}],
    )

    assert "thinking" not in payload


def test_build_chat_payload_forwards_supported_sampling_controls():
    profile = ModelProfile(
        provider="default",
        model=MODEL_NAME,
        purpose="金融结构化抽取",
        use_json_output=True,
    )

    payload = build_chat_payload(
        profile=profile,
        messages=[{"role": "user", "content": "抽取实体关系"}],
        temperature=0.1,
        top_p=0.85,
        presence_penalty=0.1,
        frequency_penalty=0.2,
    )

    assert payload["temperature"] == 0.1
    assert payload["top_p"] == 0.85
    assert payload["presence_penalty"] == 0.1
    assert payload["frequency_penalty"] == 0.2


def test_build_chat_payload_enables_web_search_tool_for_freshness_tasks():
    profile = ModelProfile(
        provider="default",
        model=MODEL_NAME,
        purpose="实时消息面搜索",
        use_web_search=True,
    )

    payload = build_chat_payload(
        profile=profile,
        messages=[{"role": "user", "content": "检索近期新闻"}],
    )

    assert payload["model"] == MODEL_NAME
    assert payload["tools"] == [{"type": "web_search"}]
    assert payload["tool_choice"] == "auto"


def test_http_gateway_routes_news_task_through_shared_model_and_base_url(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{\"events\":[]}"}}]}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)
    monkeypatch.setattr("app.services.llm_service.settings.openai_api_key", "shared-key")
    monkeypatch.setattr("app.services.llm_service.settings.openai_base_url", "https://llm-gateway.example/v1")
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", MODEL_NAME)
    monkeypatch.setattr("app.services.llm_service.settings.llm_timeout_seconds", 120, raising=False)

    content = HttpLLMGateway().complete(
        task=LLMTask.NEWS_SEARCH,
        messages=[{"role": "user", "content": "检索新闻"}],
    )

    assert content == "{\"events\":[]}"
    assert captured["url"] == "https://llm-gateway.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer shared-key"
    assert captured["headers"]["User-Agent"].startswith("Mozilla/5.0")
    assert captured["headers"]["Accept"] == "application/json"
    assert captured["timeout"] == 90
    assert captured["json"]["model"] == MODEL_NAME
    assert captured["json"]["tools"] == [{"type": "web_search"}]
    assert captured["json"]["tool_choice"] == "auto"


def test_http_gateway_forwards_supported_sampling_controls(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{\"events\":[]}"}}]}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)
    monkeypatch.setattr("app.services.llm_service.settings.openai_api_key", "shared-key")
    monkeypatch.setattr("app.services.llm_service.settings.openai_base_url", "https://llm-gateway.example/v1")
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", MODEL_NAME)

    HttpLLMGateway().complete(
        task=LLMTask.EXTRACTION,
        messages=[{"role": "user", "content": "输出 JSON"}],
        temperature=0.1,
        top_p=0.85,
        presence_penalty=0.1,
        frequency_penalty=0.2,
    )

    assert captured["json"]["temperature"] == 0.1
    assert captured["json"]["top_p"] == 0.85
    assert captured["json"]["presence_penalty"] == 0.1
    assert captured["json"]["frequency_penalty"] == 0.2


def test_http_gateway_uses_task_specific_timeout(tmp_path, monkeypatch):
    captured = {}
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=shared-key",
                "OPENAI_BASE_URL=https://llm-gateway.example/v1",
                f"LLM_MODEL={MODEL_NAME}",
                "LLM_TIMEOUT_SECONDS=120",
                "LLM_TEXT2CYPHER_TIMEOUT_SECONDS=15",
            ]
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{\"cypher\":\"MATCH (c:Company) RETURN c\"}"}}]}

    def fake_post(url, headers, json, timeout):
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)
    monkeypatch.setattr("app.services.llm_service.settings", Settings(_env_file=env_path))

    HttpLLMGateway().complete(
        task=LLMTask.TEXT2CYPHER,
        messages=[{"role": "user", "content": "查询所有公司"}],
    )

    assert captured["timeout"] == 15


def test_http_gateway_does_not_send_prompt_cache_controls(tmp_path, monkeypatch):
    captured = {}
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=shared-key",
                "OPENAI_BASE_URL=https://llm-gateway.example/v1",
                f"LLM_MODEL={MODEL_NAME}",
                "LLM_PROMPT_CACHE_KEY_PREFIX=fingraph",
                "LLM_PROMPT_CACHE_RETENTION=in_memory",
            ]
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{\"events\":[]}"}}]}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)
    monkeypatch.setattr("app.services.llm_service.settings", Settings(_env_file=env_path))

    HttpLLMGateway().complete(
        task=LLMTask.EXTRACTION,
        messages=[{"role": "user", "content": "输出 JSON"}],
    )

    assert "prompt_cache_key" not in captured["json"]
    assert "prompt_cache_retention" not in captured["json"]


def test_http_gateway_retries_transient_transport_errors(monkeypatch):
    attempts = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{\"ok\":true}"}}]}

    def fake_post(url, headers, json, timeout):
        attempts.append(url)
        if len(attempts) == 1:
            raise httpx.ConnectError("connection reset")
        return FakeResponse()

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)
    monkeypatch.setattr("app.services.llm_service.settings.openai_api_key", "shared-key")
    monkeypatch.setattr("app.services.llm_service.settings.openai_base_url", "https://llm-gateway.example/v1")
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", MODEL_NAME)
    monkeypatch.setattr("app.services.llm_service.settings.llm_timeout_seconds", 120, raising=False)

    content = HttpLLMGateway().complete(
        task=LLMTask.EXTRACTION,
        messages=[{"role": "user", "content": "输出 JSON"}],
    )

    assert content == "{\"ok\":true}"
    assert len(attempts) == 2


def test_http_gateway_uses_fallback_model_after_retryable_primary_failure(tmp_path, monkeypatch):
    attempts = []
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=shared-key",
                "OPENAI_BASE_URL=https://llm-gateway.example/v1",
                f"LLM_MODEL={MODEL_NAME}",
                "LLM_FALLBACK_MODELS=fallback-mini",
                "LLM_MAX_RETRIES=0",
            ]
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{\"ok\":true}"}}]}

    def fake_post(url, headers, json, timeout):
        attempts.append((url, json["model"]))
        if json["model"] == MODEL_NAME:
            raise httpx.ConnectError("primary offline")
        return FakeResponse()

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)
    monkeypatch.setattr("app.services.llm_service.settings", Settings(_env_file=env_path))
    monkeypatch.setattr("app.services.llm_service._LLM_CIRCUIT_BREAKERS", {}, raising=False)

    content = HttpLLMGateway().complete(
        task=LLMTask.EXTRACTION,
        messages=[{"role": "user", "content": "输出 JSON"}],
    )

    assert content == "{\"ok\":true}"
    assert attempts == [
        ("https://llm-gateway.example/v1/chat/completions", MODEL_NAME),
        ("https://llm-gateway.example/v1/chat/completions", "fallback-mini"),
    ]


def test_http_gateway_uses_fallback_base_url_after_retryable_primary_failure(tmp_path, monkeypatch):
    attempts = []
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=shared-key",
                "OPENAI_BASE_URL=https://primary.example/v1",
                f"LLM_MODEL={MODEL_NAME}",
                "OPENAI_FALLBACK_BASE_URLS=https://backup.example/v1",
                "LLM_MAX_RETRIES=0",
            ]
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{\"ok\":true}"}}]}

    def fake_post(url, headers, json, timeout):
        attempts.append(url)
        if url.startswith("https://primary.example"):
            raise httpx.ConnectError("primary offline")
        return FakeResponse()

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)
    monkeypatch.setattr("app.services.llm_service.settings", Settings(_env_file=env_path))

    content = HttpLLMGateway().complete(
        task=LLMTask.EXTRACTION,
        messages=[{"role": "user", "content": "输出 JSON"}],
    )

    assert content == "{\"ok\":true}"
    assert attempts == [
        "https://primary.example/v1/chat/completions",
        "https://backup.example/v1/chat/completions",
    ]


def test_http_gateway_opens_circuit_after_repeated_failures(tmp_path, monkeypatch):
    attempts = []
    current_time = 1_000.0
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=shared-key",
                f"LLM_MODEL={MODEL_NAME}",
                "LLM_MAX_RETRIES=0",
                "LLM_CIRCUIT_BREAKER_FAILURES=2",
                "LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS=60",
            ]
        ),
        encoding="utf-8",
    )

    def fake_post(url, headers, json, timeout):
        attempts.append(url)
        raise httpx.ConnectError("connection reset")

    monkeypatch.setattr("app.services.llm_service.httpx.post", fake_post)
    monkeypatch.setattr("app.services.llm_service.time.time", lambda: current_time)
    monkeypatch.setattr("app.services.llm_service.settings", Settings(_env_file=env_path))
    monkeypatch.setattr("app.services.llm_service._LLM_CIRCUIT_BREAKERS", {}, raising=False)

    gateway = HttpLLMGateway()
    for _ in range(2):
        with pytest.raises(httpx.ConnectError):
            gateway.complete(
                task=LLMTask.EXTRACTION,
                messages=[{"role": "user", "content": "输出 JSON"}],
            )

    with pytest.raises(RuntimeError, match="circuit breaker"):
        gateway.complete(
            task=LLMTask.EXTRACTION,
            messages=[{"role": "user", "content": "输出 JSON"}],
        )

    assert len(attempts) == 2


def test_http_gateway_requires_configured_model_name(monkeypatch):
    monkeypatch.setattr("app.services.llm_service.settings.openai_api_key", "shared-key")
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", "")

    with pytest.raises(RuntimeError, match="LLM_MODEL"):
        HttpLLMGateway().complete(
            task=LLMTask.EXTRACTION,
            messages=[{"role": "user", "content": "抽取实体关系"}],
        )


def test_http_gateway_reports_empty_non_stream_choices(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": []}

    monkeypatch.setattr("app.services.llm_service.httpx.post", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr("app.services.llm_service.settings.openai_api_key", "shared-key")
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", MODEL_NAME)

    with pytest.raises(RuntimeError, match="missing choices"):
        HttpLLMGateway().complete(
            task=LLMTask.EXTRACTION,
            messages=[{"role": "user", "content": "抽取实体关系"}],
        )


def test_http_gateway_reports_tool_calls_without_dispatcher(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "get_weather", "arguments": "{\"city\":\"上海\"}"},
                                }
                            ]
                        }
                    }
                ]
            }

    monkeypatch.setattr("app.services.llm_service.httpx.post", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr("app.services.llm_service.settings.openai_api_key", "shared-key")
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", MODEL_NAME)

    with pytest.raises(RuntimeError, match="tool_calls"):
        HttpLLMGateway().complete(
            task=LLMTask.EXTRACTION,
            messages=[{"role": "user", "content": "必须调用工具"}],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
                    },
                }
            ],
            tool_choice="required",
        )


def test_http_gateway_streams_chunks_through_shared_model_and_base_url(monkeypatch):
    captured = {}

    class FakeStreamResponse:
        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield "data: " + json.dumps({"choices": [{"delta": {"content": "第一段"}}]})
            yield "data: " + json.dumps({"choices": [{"delta": {"content": "第二段"}}]})
            yield "data: [DONE]"

    class FakeStreamContext:
        def __enter__(self):
            return FakeStreamResponse()

        def __exit__(self, exc_type, exc, traceback):
            return False

    def fake_stream(method, url, headers, json, timeout):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeStreamContext()

    monkeypatch.setattr("app.services.llm_service.httpx.stream", fake_stream)
    monkeypatch.setattr("app.services.llm_service.settings.openai_api_key", "shared-key")
    monkeypatch.setattr("app.services.llm_service.settings.openai_base_url", "https://llm-gateway.example/v1")
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", MODEL_NAME)
    monkeypatch.setattr("app.services.llm_service.settings.llm_timeout_seconds", 120, raising=False)

    chunks = list(
        HttpLLMGateway().stream_complete(
            task=LLMTask.GRAPH_RAG_STREAM,
            messages=[{"role": "user", "content": "流式回答"}],
        )
    )

    assert chunks == ["第一段", "第二段"]
    assert captured["method"] == "POST"
    assert captured["url"] == "https://llm-gateway.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer shared-key"
    assert captured["headers"]["User-Agent"].startswith("Mozilla/5.0")
    assert captured["headers"]["Accept"] == "application/json"
    assert captured["timeout"] == 120
    assert captured["json"]["model"] == MODEL_NAME
    assert captured["json"]["stream"] is True
    assert "response_format" not in captured["json"]


def test_http_gateway_stream_skips_empty_choice_chunks(monkeypatch):
    class FakeStreamResponse:
        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield "data: " + json.dumps({"choices": []})
            yield "data: " + json.dumps({"choices": [{"delta": {"content": "正文"}}]})
            yield "data: [DONE]"

    class FakeStreamContext:
        def __enter__(self):
            return FakeStreamResponse()

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr("app.services.llm_service.httpx.stream", lambda *args, **kwargs: FakeStreamContext())
    monkeypatch.setattr("app.services.llm_service.settings.openai_api_key", "shared-key")
    monkeypatch.setattr("app.services.llm_service.settings.openai_base_url", "https://llm-gateway.example/v1")
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", MODEL_NAME)

    chunks = list(
        HttpLLMGateway().stream_complete(
            task=LLMTask.GRAPH_RAG_STREAM,
            messages=[{"role": "user", "content": "流式回答"}],
        )
    )

    assert chunks == ["正文"]


def test_http_gateway_stream_retries_connection_before_first_chunk(monkeypatch):
    attempts = []

    class FakeStreamResponse:
        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield "data: " + json.dumps({"choices": [{"delta": {"content": "正文"}}]})
            yield "data: [DONE]"

    class FakeStreamContext:
        def __enter__(self):
            attempts.append("enter")
            if len(attempts) == 1:
                raise httpx.ConnectError("connection reset")
            return FakeStreamResponse()

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr("app.services.llm_service.httpx.stream", lambda *args, **kwargs: FakeStreamContext())
    monkeypatch.setattr("app.services.llm_service.settings.openai_api_key", "shared-key")
    monkeypatch.setattr("app.services.llm_service.settings.openai_base_url", "https://llm-gateway.example/v1")
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", MODEL_NAME)
    monkeypatch.setattr("app.services.llm_service.settings.llm_retry_backoff_seconds", 0)

    chunks = list(
        HttpLLMGateway().stream_complete(
            task=LLMTask.GRAPH_RAG_STREAM,
            messages=[{"role": "user", "content": "流式回答"}],
        )
    )

    assert chunks == ["正文"]
    assert attempts == ["enter", "enter"]


def test_http_gateway_stream_uses_fallback_model_before_first_chunk(tmp_path, monkeypatch):
    attempts = []
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=shared-key",
                "OPENAI_BASE_URL=https://llm-gateway.example/v1",
                f"LLM_MODEL={MODEL_NAME}",
                "LLM_FALLBACK_MODELS=fallback-mini",
                "LLM_MAX_RETRIES=0",
            ]
        ),
        encoding="utf-8",
    )

    class FakeStreamResponse:
        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield "data: " + json.dumps({"choices": [{"delta": {"content": "正文"}}]})
            yield "data: [DONE]"

    class FakeStreamContext:
        def __init__(self, model):
            self.model = model

        def __enter__(self):
            attempts.append(self.model)
            if self.model == MODEL_NAME:
                raise httpx.ConnectError("primary offline")
            return FakeStreamResponse()

        def __exit__(self, exc_type, exc, traceback):
            return False

    def fake_stream(method, url, headers, json, timeout):
        return FakeStreamContext(json["model"])

    monkeypatch.setattr("app.services.llm_service.httpx.stream", fake_stream)
    monkeypatch.setattr("app.services.llm_service.settings", Settings(_env_file=env_path))

    chunks = list(
        HttpLLMGateway().stream_complete(
            task=LLMTask.GRAPH_RAG_STREAM,
            messages=[{"role": "user", "content": "流式回答"}],
        )
    )

    assert chunks == ["正文"]
    assert attempts == [MODEL_NAME, "fallback-mini"]
