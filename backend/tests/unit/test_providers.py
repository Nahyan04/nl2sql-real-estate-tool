from types import SimpleNamespace

from app.api.routes import providers as provider_routes
from app.config import Settings


def settings(**overrides):
    return Settings(database_url="postgresql://example.invalid/test", readonly_db_password="unused", **overrides)


def test_disabled_ollama_does_not_contact_endpoint(monkeypatch):
    monkeypatch.setattr(provider_routes, "Client", lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected probe")))
    assert provider_routes.ollama_status(settings(ollama_enabled=False)) == "disabled"


def test_ollama_requires_configured_model_and_passes_auth_header(monkeypatch):
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def list(self):
            return SimpleNamespace(models=[SimpleNamespace(model="qwen3.5:9b")])

    monkeypatch.setattr(provider_routes, "Client", Client)
    configured = settings(ollama_enabled=True, ollama_model="qwen3.5:9b", ollama_api_key="test-token")
    assert provider_routes.ollama_status(configured) == "ready"
    assert captured["headers"] == {"Authorization": "Bearer test-token"}
    assert provider_routes.ollama_status(settings(ollama_enabled=True, ollama_model="missing")) == "model_missing"


def test_unreachable_ollama_is_unavailable(monkeypatch):
    monkeypatch.setattr(provider_routes, "Client", lambda **kwargs: (_ for _ in ()).throw(OSError("offline")))
    assert provider_routes.ollama_status(settings(ollama_enabled=True)) == "unavailable"
