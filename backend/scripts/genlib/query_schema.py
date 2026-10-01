"""Prepare the source-backed query surface in an explicitly selected staging DB."""
from hashlib import sha256
from pathlib import Path

from sqlalchemy import text

from .source_contract import ContractError

MIGRATION = Path(__file__).resolve().parents[2] / 'db/bayan_query_v1.sql'


def prepare_query_schema(engine, expected_database: str, snapshot_id: str, *, restrict_readonly: bool = False) -> None:
    if not expected_database.startswith('bayan_staging_'):
        raise ContractError('Only an explicitly named bayan_staging_ database is supported')
    with engine.begin() as connection:
        if connection.execute(text('SELECT current_database()')).scalar_one() != expected_database:
            raise ContractError('Connected database differs from explicit target')
        connection.execute(text('SELECT pg_advisory_xact_lock(836492170)'))
        status = connection.execute(text('SELECT status FROM adrec_intake.snapshots WHERE snapshot_id=:id'), {'id': snapshot_id}).scalar_one_or_none()
        if status != 'validated':
            raise ContractError('Snapshot must have completed source validation')
        sources = connection.execute(text('''SELECT s.source_rows, count(o.source_row) FROM adrec_intake.sources s
            LEFT JOIN adrec_intake.observations o USING(snapshot_id,source_file)
            WHERE s.snapshot_id=:id GROUP BY s.source_file,s.source_rows'''), {'id': snapshot_id}).all()
        if len(sources) != 31 or any(expected != actual for expected, actual in sources):
            raise ContractError('Snapshot source accounting is incomplete')
        digest = sha256(MIGRATION.read_bytes()).hexdigest()
        exists = connection.execute(text("SELECT to_regclass('bayan.schema_version')")).scalar_one()
        if exists:
            version = connection.execute(text('SELECT version,migration_sha256 FROM bayan.schema_version')).all()
            if version != [(1, digest)]:
                raise ContractError('Query schema migration mismatch; explicit upgrade required')
        else:
            connection.execute(text(MIGRATION.read_text()))
            connection.execute(text('INSERT INTO bayan.schema_version VALUES (1,:hash)'), {'hash': digest})
        connection.execute(text('''INSERT INTO bayan.active_snapshot(singleton,snapshot_id) VALUES (true,:id)
            ON CONFLICT(singleton) DO UPDATE SET snapshot_id=excluded.snapshot_id'''), {'id': snapshot_id})
        if restrict_readonly:
            grant_query_role(connection)


def grant_query_role(connection, connection_limit: int = 4) -> None:
    """Grant an existing dedicated role only the four product views."""
    if not 1 <= connection_limit <= 16:
        raise ContractError("Connection limit must be between 1 and 16")
    role = connection.execute(text("SELECT rolsuper,rolcreaterole,rolcreatedb,rolbypassrls FROM pg_roles WHERE rolname='nl2sql_readonly'")).first()
    if role is None or any(role):
        raise ContractError('A dedicated non-privileged nl2sql_readonly role is required')
    inherited = connection.execute(text("SELECT count(*) FROM pg_auth_members WHERE member='nl2sql_readonly'::regrole")).scalar_one()
    if inherited:
        raise ContractError('Read-only role must not inherit other roles')
    connection.execute(text(f'ALTER ROLE nl2sql_readonly CONNECTION LIMIT {int(connection_limit)}'))
    connection.execute(text('REVOKE ALL ON SCHEMA public, adrec_intake FROM nl2sql_readonly'))
    connection.execute(text('REVOKE ALL ON ALL TABLES IN SCHEMA public, adrec_intake, bayan FROM nl2sql_readonly'))
    connection.execute(text('GRANT USAGE ON SCHEMA bayan TO nl2sql_readonly'))
    connection.execute(text('GRANT SELECT ON bayan.transactions,bayan.price_indices,bayan.rental_observations,bayan.dataset_coverage TO nl2sql_readonly'))
    forbidden = connection.execute(text("""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('public','adrec_intake') AND c.relkind IN ('r','v','m','p')
        AND has_table_privilege('nl2sql_readonly',c.oid,'SELECT')""")).scalar_one()
    if forbidden:
        raise ContractError('Read-only role still has legacy/intake access through ownership or PUBLIC grants')
