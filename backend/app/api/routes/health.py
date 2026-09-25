from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


@router.get("/health")
def health_check(request: Request) -> dict[str, str]:
    engine = request.app.state.engine
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_status = "ok"
    except SQLAlchemyError:
        database_status = "error"
    return {"status": "ok", "database": database_status}


@router.get("/ready")
def readiness(request: Request):
    from fastapi.responses import JSONResponse
    from app.services.product_schema import introspect_product_schema
    try:
        schema = introspect_product_schema(request.app.state.engine)
        return {"status": "ready", "snapshot_id": schema["snapshot_id"]}
    except (SQLAlchemyError, ValueError):
        return JSONResponse(status_code=503, content={"status": "not_ready"})
