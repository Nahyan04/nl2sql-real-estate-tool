from __future__ import annotations

from app.config import get_settings
from app.core.database import READONLY_ROLE, get_engine, get_readonly_engine


def test_readonly_engine_connects_as_the_readonly_role() -> None:
    assert get_readonly_engine().url.username == READONLY_ROLE


def test_readonly_engine_uses_the_readonly_password() -> None:
    url = get_readonly_engine().url
    assert url.password == get_settings().readonly_db_password


def test_readonly_engine_targets_the_same_database_as_the_app_engine() -> None:
    readonly, app = get_readonly_engine().url, get_engine().url
    assert (readonly.host, readonly.port, readonly.database) == (app.host, app.port, app.database)


def test_readonly_engine_is_not_the_app_engine() -> None:
    assert get_readonly_engine() is not get_engine()
