from __future__ import annotations

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama

from app.config import Settings
from app.core.llm import get_chat_model


def _settings(**overrides) -> Settings:
    values = {
        "database_url": "postgresql://postgres:postgres@localhost:5432/postgres",
        "readonly_db_password": "pw",
        "llm_provider": "anthropic",
        "llm_base_url": "http://localhost:11434",
        "anthropic_model": "claude-sonnet-5",
        "ollama_model": "qwen2.5-coder:7b",
        "anthropic_api_key": "sk-test",
    }
    values.update(overrides)
    return Settings(**values)


def test_anthropic_provider_returns_chat_anthropic() -> None:
    assert isinstance(get_chat_model("anthropic", _settings()), ChatAnthropic)


def test_anthropic_model_comes_from_settings() -> None:
    model = get_chat_model("anthropic", _settings(anthropic_model="claude-opus-5"))
    assert model.model == "claude-opus-5"


def test_anthropic_temperature_is_zero() -> None:
    assert get_chat_model("anthropic", _settings()).temperature == 0


def test_anthropic_api_key_comes_from_settings() -> None:
    model = get_chat_model("anthropic", _settings(anthropic_api_key="sk-plumbed"))
    assert model.anthropic_api_key.get_secret_value() == "sk-plumbed"


def test_ollama_provider_returns_chat_ollama() -> None:
    assert isinstance(get_chat_model("ollama", _settings()), ChatOllama)


def test_ollama_model_comes_from_settings() -> None:
    model = get_chat_model("ollama", _settings(ollama_model="llama3.1:8b"))
    assert model.model == "llama3.1:8b"


def test_ollama_base_url_comes_from_settings() -> None:
    model = get_chat_model("ollama", _settings(llm_base_url="http://ollama:11434"))
    assert model.base_url == "http://ollama:11434"


def test_ollama_temperature_is_zero() -> None:
    assert get_chat_model("ollama", _settings()).temperature == 0


def test_missing_provider_falls_back_to_settings_provider() -> None:
    assert isinstance(get_chat_model(None, _settings(llm_provider="ollama")), ChatOllama)


def test_request_provider_overrides_settings_provider() -> None:
    assert isinstance(get_chat_model("ollama", _settings(llm_provider="anthropic")), ChatOllama)


def test_provider_name_is_case_insensitive() -> None:
    assert isinstance(get_chat_model("Anthropic", _settings()), ChatAnthropic)


def test_unknown_provider_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown llm provider"):
        get_chat_model("openai", _settings())
