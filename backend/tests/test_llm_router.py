from app.services.llm_service import (
    LLMTask,
    ModelProfile,
    build_chat_payload,
    select_model_profile,
)
from app.config import Settings


def test_settings_enable_llm_by_default_without_env_toggle(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")

    settings = Settings(_env_file=env_path)

    assert settings.llm_enabled is True


def test_select_model_profile_routes_structured_finance_tasks_to_deepseek():
    profile = select_model_profile(LLMTask.EXTRACTION)

    assert profile.provider == "deepseek"
    assert profile.model == "deepseek-v4-flash"
    assert profile.use_json_output is True

    assert select_model_profile(LLMTask.JUDGE).provider == "deepseek"
    assert select_model_profile(LLMTask.TEXT2CYPHER).provider == "deepseek"
    assert select_model_profile(LLMTask.STOCK_ANALYSIS).provider == "deepseek"


def test_select_model_profile_routes_freshness_tasks_to_grok():
    profile = select_model_profile(LLMTask.NEWS_SEARCH)

    assert profile.provider == "grok"
    assert profile.model == "grok-4.20-fast"
    assert profile.use_web_search is True
    assert select_model_profile(LLMTask.MARKET_NEWS).provider == "grok"


def test_build_chat_payload_uses_json_response_format_for_structured_tasks():
    profile = ModelProfile(
        provider="deepseek",
        model="deepseek-v4-flash",
        purpose="金融结构化抽取",
        use_json_output=True,
    )

    payload = build_chat_payload(
        profile=profile,
        messages=[{"role": "user", "content": "抽取实体关系"}],
        temperature=0,
    )

    assert payload["model"] == "deepseek-v4-flash"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0


def test_build_chat_payload_enables_grok_web_search_tool_for_freshness_tasks():
    profile = ModelProfile(
        provider="grok",
        model="grok-4.20-fast",
        purpose="实时消息面搜索",
        use_web_search=True,
    )

    payload = build_chat_payload(
        profile=profile,
        messages=[{"role": "user", "content": "检索近期新闻"}],
    )

    assert payload["model"] == "grok-4.20-fast"
    assert payload["tools"] == [{"type": "web_search"}]
