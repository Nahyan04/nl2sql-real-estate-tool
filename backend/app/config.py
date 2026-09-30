from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    readonly_db_password: str
    llm_provider: str = "anthropic"
    llm_base_url: str = "http://localhost:11434"
    anthropic_model: str = "claude-sonnet-5"
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_reasoning: bool | None = None
    ollama_enabled: bool = False
    ollama_api_key: str | None = None
    anthropic_api_key: str | None = None
    embedding_enabled: bool = False
    query_row_limit: int = Field(default=500, ge=1, le=5000)
    query_timeout_s: int = Field(default=5, ge=1, le=30)
    query_result_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    query_cell_bytes: int = Field(default=65_536, ge=256, le=1_048_576)
    query_connections: int = Field(default=4, ge=1, le=16)
    query_pool_wait_s: float = Field(default=1, gt=0, le=5)
    model_call_timeout_s: float = Field(default=12, gt=0, le=60)
    request_timeout_s: float = Field(default=25, gt=0, le=120)
    model_max_output_tokens: int = Field(default=1200, ge=128, le=4096)
    model_generation_attempts: int = Field(default=2, ge=1, le=3)
    model_concurrency: int = Field(default=2, ge=1, le=16)
    model_queue_size: int = Field(default=4, ge=0, le=64)
    model_queue_wait_s: float = Field(default=2, gt=0, le=10)
    request_session_minute_limit: int = Field(default=30, ge=1)
    request_session_day_limit: int = Field(default=300, ge=1)
    request_ip_minute_limit: int = Field(default=120, ge=1)
    request_ip_day_limit: int = Field(default=1200, ge=1)
    request_global_concurrency: int = Field(default=8, ge=1, le=128)
    trusted_proxy_cidrs: str = ""
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "none", "strict"] = "lax"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
