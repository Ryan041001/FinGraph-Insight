import json

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
    assert captured["timeout"] == 120
    assert captured["json"]["model"] == MODEL_NAME
    assert captured["json"]["tools"] == [{"type": "web_search"}]


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
