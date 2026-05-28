from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="password", alias="NEO4J_PASSWORD")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    llm_model: str = Field(default="deepseek-chat", alias="LLM_MODEL")
    llm_model_deepseek: str = Field(default="deepseek-v4-flash", alias="LLM_MODEL_DEEPSEEK")
    llm_model_grok: str = Field(default="grok-4.20-fast", alias="LLM_MODEL_GROK")
    llm_enabled: bool = Field(default=False, alias="LLM_ENABLED")
    graph_backend: str = Field(default="memory", alias="GRAPH_BACKEND")
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    text2cypher_max_limit: int = Field(default=100, alias="TEXT2CYPHER_MAX_LIMIT")
    text2cypher_timeout_seconds: int = Field(default=5, alias="TEXT2CYPHER_TIMEOUT_SECONDS")


settings = Settings()
