from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.config import Settings

ANTHROPIC = "anthropic"
OLLAMA = "ollama"


def message_text(message: Any) -> str:
    """Flatten a chat response to text; hosted providers may return content blocks."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)


def get_chat_model(provider: str | None, settings: Settings) -> BaseChatModel:
    """Build the chat model for a request; `provider` overrides the configured default."""
    name = (provider or settings.llm_provider).strip().lower()

    if name == ANTHROPIC:
        return ChatAnthropic(
            model=settings.anthropic_model,
            temperature=0,
            api_key=settings.anthropic_api_key,
            max_tokens=settings.model_max_output_tokens,
            timeout=settings.model_call_timeout_s,
            max_retries=0,
        )

    if name == OLLAMA:
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.llm_base_url,
            temperature=0,
            num_predict=settings.model_max_output_tokens,
            sync_client_kwargs={"timeout": settings.model_call_timeout_s},
            async_client_kwargs={"timeout": settings.model_call_timeout_s},
        )

    raise ValueError(f"unknown llm provider: {name!r}")
