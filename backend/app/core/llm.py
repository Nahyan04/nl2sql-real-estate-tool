from __future__ import annotations

import logging
from typing import Any

from anthropic import APITimeoutError
from httpx import TimeoutException
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.config import Settings

ANTHROPIC = "anthropic"
OLLAMA = "ollama"
logger = logging.getLogger(__name__)


def provider_failure(exc: Exception) -> dict[str, Any]:
    """Keep provider failures actionable without exposing SDK response bodies."""
    status = getattr(exc, "status_code", None)
    if isinstance(exc, (APITimeoutError, TimeoutException, TimeoutError)) or status in {408, 504}:
        return {"type": "PROVIDER_TIMEOUT", "detail": "The selected provider exceeded the model call time limit."}
    if status == 429:
        failure = {"type": "PROVIDER_RATE_LIMIT", "detail": "The selected provider's request or account limit was reached."}
        response = getattr(exc, "response", None)
        value = getattr(response, "headers", {}).get("retry-after", "")
        try:
            seconds = int(value)
            if 0 < seconds <= 3600:
                failure["retry_after"] = seconds
        except (TypeError, ValueError):
            pass
        return failure
    if status in {401, 402, 403, 404}:
        return {"type": "PROVIDER_CONFIGURATION_ERROR", "detail": "Check the selected provider's server credentials, model access and billing configuration."}
    if status in {400, 413, 422}:
        return {"type": "PROVIDER_REQUEST_ERROR", "detail": "The selected provider rejected the request; check server configuration and provider account limits."}
    return {"type": "PROVIDER_UNAVAILABLE", "detail": "The selected provider could not be reached or is temporarily unavailable."}


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
        logger.info("anthropic model configured model=%s temperature=%s", settings.anthropic_model, settings.model_temperature)
        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            max_tokens=settings.model_max_output_tokens,
            temperature=settings.model_temperature,
            timeout=settings.model_call_timeout_s,
            max_retries=0,
        )

    if name == OLLAMA:
        logger.info("ollama model configured model=%s reasoning=%s", settings.ollama_model, settings.ollama_reasoning)
        client_kwargs = {"headers": {"Authorization": f"Bearer {settings.ollama_api_key}"}} if settings.ollama_api_key else {}
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.llm_base_url,
            temperature=0,
            reasoning=settings.ollama_reasoning,
            num_predict=settings.model_max_output_tokens,
            client_kwargs=client_kwargs,
            sync_client_kwargs={"timeout": settings.model_call_timeout_s},
            async_client_kwargs={"timeout": settings.model_call_timeout_s},
        )

    raise ValueError(f"unknown llm provider: {name!r}")
