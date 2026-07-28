from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    readonly_db_password: str
    llm_provider: str = "anthropic"
    llm_base_url: str = "http://localhost:11434"
    anthropic_model: str = "claude-sonnet-5"
    ollama_model: str = "qwen2.5-coder:7b"
    anthropic_api_key: str | None = None
    embedding_enabled: bool = False
    query_row_limit: int = 500
    query_timeout_s: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
