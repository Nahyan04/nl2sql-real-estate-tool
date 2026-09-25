from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.services.product_schema import introspect_product_schema

router = APIRouter()


@router.get("/schema")
def schema(request: Request) -> dict[str, Any]:
    return introspect_product_schema(request.app.state.engine)
