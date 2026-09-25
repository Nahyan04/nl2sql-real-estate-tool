from __future__ import annotations

from functools import lru_cache

from pydantic import Field
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
    query_row_limit: int = Field(default=500, ge=1, le=5000)
    query_timeout_s: int = Field(default=5, ge=1, le=30)
    query_result_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    query_cell_bytes: int = Field(default=65_536, ge=256, le=1_048_576)
    query_connections: int = Field(default=4, ge=1, le=16)
    query_pool_wait_s: float = Field(default=1, gt=0, le=5)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
