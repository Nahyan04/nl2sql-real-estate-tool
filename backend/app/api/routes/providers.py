from __future__ import annotations

from fastapi import APIRouter, Depends
from ollama import Client

from app.config import Settings, get_settings

router = APIRouter()


def ollama_status(settings: Settings) -> str:
    if not settings.ollama_enabled:
        return "disabled"
    headers = {"Authorization": f"Bearer {settings.ollama_api_key}"} if settings.ollama_api_key else None
    try:
        models = Client(host=settings.llm_base_url, headers=headers, timeout=2).list().models
    except Exception:  # noqa: BLE001 - endpoint and transport failures have one public status
        return "unavailable"
    return "ready" if any(model.model == settings.ollama_model for model in models) else "model_missing"


@router.get("/providers")
def providers(settings: Settings = Depends(get_settings)) -> dict[str, dict[str, str | bool]]:
    local_status = ollama_status(settings)
    return {
        "anthropic": {"available": bool(settings.anthropic_api_key), "status": "configured" if settings.anthropic_api_key else "not_configured"},
        "ollama": {"available": local_status == "ready", "status": local_status},
    }
