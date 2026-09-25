"""Fresh application runtime checks on an explicitly selected disposable target."""
import os
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from langchain_core.messages import AIMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.config import Settings
from app.services.product_schema import introspect_product_schema, PRODUCT_RELATIONS
from app.services.graph import run_pipeline
from app.services.executor import execute_readonly
from scripts.genlib.query_schema import prepare_query_schema, grant_query_role


@pytest.fixture(scope='module')
def runtime():
    url = os.environ.get('BAYAN_DISPOSABLE_STAGING_URL')
    if not url:
        pytest.skip('Explicit disposable staging target required')
    engine = create_engine(url)
    database = engine.url.database
    assert database.startswith('bayan_staging_')
    prepare_query_schema(engine, database, '2026-09-24')
    prepare_query_schema(engine, database, '2026-09-24')
    with engine.begin() as connection:
        if not connection.execute(text("SELECT 1 FROM pg_roles WHERE rolname='nl2sql_readonly'")).scalar():
            connection.execute(text('CREATE ROLE nl2sql_readonly LOGIN'))
        grant_query_role(connection)
    readonly = create_engine(engine.url.set(username='nl2sql_readonly'))
    yield engine, readonly, Settings(database_url=url, readonly_db_password='unused')
    readonly.dispose()
    engine.dispose()


class Model:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = 0
        self.system = ''

    def invoke(self, messages):
        self.calls += 1
        self.system = messages[0].content
        return AIMessage(content=next(self.responses, ''))


def test_introspection_exposes_only_source_views(runtime):
    schema = introspect_product_schema(runtime[0])
    assert {t['name'] for t in schema['tables']} == PRODUCT_RELATIONS
    assert schema['snapshot_id'] == '2026-09-24'
    transaction = next(t for t in schema['tables'] if t['name']=='transactions')
    assert {'district','community','project_name','sold_share','sale_type'} <= {c['name'] for c in transaction['columns']}


def test_fresh_pipeline_executes_with_exact_evidence(runtime):
    engine, readonly, settings = runtime
    model = Model('<sql>SELECT count(*) AS sales_observations FROM transactions</sql>', '122936 exported sales observations.')
    state = run_pipeline('How many exported sales observations?', chat_model=model, engine=engine, engine_ro=readonly, settings=settings)
    assert not state['failure']
    assert state['exec_result'].rows == [[122936]]
    assert state['tables_used'] == ['transactions']
    assert state['sql'] == state['exec_result'].executed_sql
    assert 'LIMIT 501' in state['sql']


def test_unsupported_stops_without_retry_or_execution(runtime):
    engine, readonly, settings = runtime
    model = Model('<unsupported>Lender-level mortgage records are unavailable.</unsupported>')
    state = run_pipeline('Mortgage totals by lender?', chat_model=model, engine=engine, engine_ro=readonly, settings=settings)
    assert state['failure']['type'] == 'UNSUPPORTED'
    assert state['exec_result'] is None and model.calls == 1


def test_synthetic_relation_never_executes(runtime):
    engine, readonly, settings = runtime
    model = Model(*(['<sql>SELECT * FROM mortgages</sql>']*3))
    state = run_pipeline('Mortgage totals?', chat_model=model, engine=engine, engine_ro=readonly, settings=settings)
    assert state['failure']['type'] == 'UNSAFE_SQL'
    assert state['exec_result'] is None


def test_role_denied_raw_rows_and_write_privileges(runtime):
    _, readonly, _ = runtime
    with readonly.connect() as connection:
        with pytest.raises(DBAPIError):
            connection.execute(text('SELECT * FROM adrec_intake.observations LIMIT 1'))
        connection.rollback()
        assert not connection.execute(text("SELECT has_table_privilege(current_user,'bayan.transactions','INSERT')")).scalar_one()
    result = execute_readonly(readonly, 'SELECT source_rows FROM dataset_coverage LIMIT 1')
    assert result.row_count == 1
