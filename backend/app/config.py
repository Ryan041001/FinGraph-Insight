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
    llm_model: str = Field(default="", alias="LLM_MODEL")
    llm_timeout_seconds: int = Field(default=120, alias="LLM_TIMEOUT_SECONDS")
    graph_backend: str = Field(default="memory", alias="GRAPH_BACKEND")
    market_live_enabled: bool = Field(default=False, alias="MARKET_LIVE_ENABLED")
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    akshare_update_cron: str = Field(default="0 */6 * * *", alias="AKSHARE_UPDATE_CRON")
    text2cypher_max_limit: int = Field(default=100, alias="TEXT2CYPHER_MAX_LIMIT")
    text2cypher_timeout_seconds: int = Field(default=5, alias="TEXT2CYPHER_TIMEOUT_SECONDS")

    @property
    def llm_enabled(self) -> bool:
        return True


settings = Settings()
