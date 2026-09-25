"""Install the shared request limiter tables in an explicitly named database."""

import argparse
from pathlib import Path

from sqlalchemy import text

from app.core.database import get_engine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, help="Expected target database name")
    args = parser.parse_args()

    engine = get_engine()
    migration = Path(__file__).resolve().parents[1] / "db/bayan_runtime_v1.sql"
    with engine.begin() as connection:
        actual = connection.execute(text("SELECT current_database()")).scalar_one()
        if actual != args.database:
            raise SystemExit("Connected database does not match --database")
        connection.exec_driver_sql(migration.read_text())
    print(f"Shared request limiter store ready in {args.database}")


if __name__ == "__main__":
    main()
