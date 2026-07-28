from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url

from app.config import get_settings

READONLY_ROLE = "nl2sql_readonly"


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_readonly_engine() -> Engine:
    """Engine for generated SQL — same database, but as a role that can only SELECT."""
    settings = get_settings()
    url = make_url(settings.database_url).set(
        username=READONLY_ROLE,
        password=settings.readonly_db_password,
    )
    return create_engine(url, pool_pre_ping=True)
