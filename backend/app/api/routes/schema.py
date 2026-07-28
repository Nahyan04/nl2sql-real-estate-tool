from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.services.schema_introspector import introspect_schema

router = APIRouter()


@router.get("/schema")
def schema(request: Request) -> dict[str, Any]:
    return introspect_schema(request.app.state.engine)
