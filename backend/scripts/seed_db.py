from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.core.database import get_engine

SCHEMA_SQL = PROJECT_ROOT / "db" / "schema.sql"
REFERENCE_SEED_SQL = PROJECT_ROOT / "db" / "reference_seed.sql"

READONLY_ROLE = "nl2sql_readonly"


def reset_schema(connection) -> None:
    connection.execute(text("DROP SCHEMA public CASCADE"))
    connection.execute(text("CREATE SCHEMA public"))


def apply_sql_file(connection, path: Path) -> None:
    connection.execute(text(path.read_text()))


def ensure_readonly_role(connection, database: str, password: str) -> None:
    role_exists = connection.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
        {"role": READONLY_ROLE},
    ).scalar_one_or_none()
    if role_exists:
        connection.execute(
            text(f"ALTER ROLE {READONLY_ROLE} LOGIN PASSWORD :password"),
            {"password": password},
        )
    else:
        connection.execute(
            text(f"CREATE ROLE {READONLY_ROLE} LOGIN PASSWORD :password"),
            {"password": password},
        )
    connection.execute(text(f"GRANT CONNECT ON DATABASE {database} TO {READONLY_ROLE}"))
    connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {READONLY_ROLE}"))
    connection.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {READONLY_ROLE}"))
    connection.execute(
        text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {READONLY_ROLE}")
    )


def main() -> None:
    settings = get_settings()
    engine = get_engine()
    try:
        with engine.begin() as connection:
            reset_schema(connection)
            apply_sql_file(connection, SCHEMA_SQL)
            apply_sql_file(connection, REFERENCE_SEED_SQL)
            ensure_readonly_role(connection, engine.url.database, settings.readonly_db_password)
        print("schema applied and reference data seeded")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
