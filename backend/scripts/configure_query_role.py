"""Configure the dedicated query role after restoring a verified fresh snapshot."""
import argparse
import sys
from pathlib import Path
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.core.database import get_engine
from app.services.product_schema import introspect_product_schema
from scripts.genlib.query_schema import grant_query_role


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-database', required=True)
    args = parser.parse_args()
    settings = get_settings()
    engine = get_engine()
    try:
        introspect_product_schema(engine)
        with engine.begin() as connection:
            if connection.execute(text('SELECT current_database()')).scalar_one() != args.expected_database:
                raise ValueError('Configured database does not match the explicit target')
            if connection.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")).scalar_one():
                raise ValueError('Unexpected public tables remain; review before configuring fresh runtime')
            exists = connection.execute(text("SELECT 1 FROM pg_roles WHERE rolname='nl2sql_readonly'")).scalar()
            command = 'ALTER' if exists else 'CREATE'
            connection.execute(text(f'{command} ROLE nl2sql_readonly LOGIN PASSWORD :password'), {'password': settings.readonly_db_password})
            grant_query_role(connection, settings.query_connections)
        print('Fresh-data read-only role configured')
    except Exception as exc:
        parser.exit(1, f'Role configuration failed ({type(exc).__name__}); transaction rolled back.\n')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
