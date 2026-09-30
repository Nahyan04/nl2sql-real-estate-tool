"""Grant the API only snapshot metadata and shared limiter access."""

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.core.database import get_engine
from app.services.product_schema import introspect_product_schema


ROLE = "nl2sql_runtime"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-database", required=True)
    args = parser.parse_args()

    settings = get_settings()
    if not settings.runtime_db_password:
        parser.error("Set RUNTIME_DB_PASSWORD in backend/.env before configuring the role")

    engine = get_engine()
    try:
        introspect_product_schema(engine)
        with engine.begin() as connection:
            database = connection.execute(text("SELECT current_database()")).scalar_one()
            if database != args.expected_database:
                raise ValueError("Configured database does not match the explicit target")
            if connection.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")).scalar_one():
                raise ValueError("Unexpected public tables remain")
            runtime_store = connection.execute(text("""SELECT
                to_regclass('bayan_runtime.request_buckets') IS NOT NULL
                AND to_regclass('bayan_runtime.request_leases') IS NOT NULL""")).scalar_one()
            if not runtime_store:
                raise ValueError("Initialize the shared request limiter store first")

            existing = connection.execute(text("""SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls
                FROM pg_roles WHERE rolname=:role"""), {"role": ROLE}).first()
            if existing and any(existing):
                raise ValueError("Runtime role has privileged attributes")
            if existing:
                memberships = connection.execute(text("""SELECT count(*) FROM pg_auth_members
                    WHERE member=(SELECT oid FROM pg_roles WHERE rolname=:role)"""), {"role": ROLE}).scalar_one()
                if memberships:
                    raise ValueError("Runtime role inherits another role")
            command = "ALTER" if existing else "CREATE"
            connection.execute(text(f"{command} ROLE {ROLE} LOGIN NOINHERIT PASSWORD :password"),
                               {"password": settings.runtime_db_password})

            connection.execute(text(f"REVOKE ALL ON SCHEMA public, adrec_intake, bayan, bayan_runtime FROM {ROLE}"))
            connection.execute(text(f"REVOKE ALL ON ALL TABLES IN SCHEMA public, adrec_intake, bayan, bayan_runtime FROM {ROLE}"))
            connection.execute(text(f"GRANT USAGE ON SCHEMA adrec_intake, bayan, bayan_runtime TO {ROLE}"))
            connection.execute(text(f"GRANT SELECT ON adrec_intake.snapshots TO {ROLE}"))
            connection.execute(text("""GRANT SELECT ON
                bayan.schema_version, bayan.active_snapshot,
                bayan.transactions, bayan.price_indices,
                bayan.rental_observations, bayan.dataset_coverage
                TO nl2sql_runtime"""))
            connection.execute(text("""GRANT SELECT, INSERT, UPDATE, DELETE ON
                bayan_runtime.request_buckets, bayan_runtime.request_leases
                TO nl2sql_runtime"""))

            forbidden = connection.execute(text("""SELECT count(*) FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname IN ('public','adrec_intake','bayan','bayan_runtime')
                  AND c.relkind IN ('r','v','m','p')
                  AND (
                    (n.nspname='adrec_intake' AND c.relname<>'snapshots'
                     AND has_table_privilege('nl2sql_runtime',c.oid,'SELECT'))
                    OR (n.nspname='public' AND has_table_privilege('nl2sql_runtime',c.oid,'SELECT'))
                    OR (n.nspname='bayan' AND c.relname NOT IN
                        ('schema_version','active_snapshot','transactions','price_indices',
                         'rental_observations','dataset_coverage')
                        AND has_table_privilege('nl2sql_runtime',c.oid,'SELECT'))
                    OR (n.nspname<>'bayan_runtime' AND has_table_privilege(
                        'nl2sql_runtime',c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'))
                    OR (n.nspname='bayan_runtime' AND c.relname NOT IN
                        ('request_buckets','request_leases') AND has_table_privilege(
                            'nl2sql_runtime',c.oid,'SELECT,INSERT,UPDATE,DELETE'))
                  )""")).scalar_one()
            if forbidden:
                raise ValueError("Runtime role retains unexpected data access")
        print(f"Restricted API runtime role ready in {database}")
    except Exception as exc:
        parser.exit(1, f"Runtime role configuration failed ({type(exc).__name__}); transaction rolled back.\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
