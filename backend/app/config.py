from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="password", alias="NEO4J_PASSWORD")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_fallback_base_urls: str = Field(default="", alias="OPENAI_FALLBACK_BASE_URLS")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    llm_fallback_models: str = Field(default="", alias="LLM_FALLBACK_MODELS")
    llm_timeout_seconds: int = Field(default=120, alias="LLM_TIMEOUT_SECONDS")
    llm_text2cypher_timeout_seconds: int = Field(default=45, alias="LLM_TEXT2CYPHER_TIMEOUT_SECONDS")
    llm_news_timeout_seconds: int = Field(default=90, alias="LLM_NEWS_TIMEOUT_SECONDS")
    llm_stream_timeout_seconds: int = Field(default=120, alias="LLM_STREAM_TIMEOUT_SECONDS")
    llm_max_retries: int = Field(default=1, alias="LLM_MAX_RETRIES")
    llm_retry_backoff_seconds: float = Field(default=0.2, alias="LLM_RETRY_BACKOFF_SECONDS")
    llm_circuit_breaker_failures: int = Field(default=3, alias="LLM_CIRCUIT_BREAKER_FAILURES")
    llm_circuit_breaker_cooldown_seconds: int = Field(default=30, alias="LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS")
    graph_backend: str = Field(default="memory", alias="GRAPH_BACKEND")
    market_live_enabled: bool = Field(default=True, alias="MARKET_LIVE_ENABLED")
    market_kline_cache_ttl_seconds: int = Field(default=300, alias="MARKET_KLINE_CACHE_TTL_SECONDS")
    market_kline_cache_dir: str = Field(default="", alias="MARKET_KLINE_CACHE_DIR")
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    akshare_update_cron: str = Field(default="0 */6 * * *", alias="AKSHARE_UPDATE_CRON")
    text2cypher_max_limit: int = Field(default=100, alias="TEXT2CYPHER_MAX_LIMIT")
    text2cypher_timeout_seconds: int = Field(default=5, alias="TEXT2CYPHER_TIMEOUT_SECONDS")
    cors_allow_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ALLOW_ORIGINS",
    )
    stock_analysis_cache_max_size: int = Field(default=64, alias="STOCK_ANALYSIS_CACHE_MAX_SIZE")
    job_run_history_max_size: int = Field(default=50, alias="JOB_RUN_HISTORY_MAX_SIZE")
    startup_preload_dataset: bool = Field(default=True, alias="STARTUP_PRELOAD_DATASET")
    startup_refresh_akshare: bool = Field(default=False, alias="STARTUP_REFRESH_AKSHARE")

    @property
    def llm_enabled(self) -> bool:
        return True


settings = Settings()
