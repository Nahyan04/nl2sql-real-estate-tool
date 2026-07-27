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
