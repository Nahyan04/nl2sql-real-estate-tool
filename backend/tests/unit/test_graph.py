import pytest
from langchain_core.messages import AIMessage
from app.services import graph
from app.services.graph import run_pipeline
from app.services.schema_introspector import introspect_schema


class Model:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return AIMessage(content=next(self.responses, ''))


@pytest.fixture
def run(sqlite_engine, monkeypatch):
    monkeypatch.setattr(graph, 'introspect_product_schema', lambda _: introspect_schema(sqlite_engine))
    def invoke(*responses, dry_run=False):
        model = Model(*responses)
        return run_pipeline('sales count', chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine, dry_run=dry_run), model
    return invoke


def test_pipeline_returns_executed_evidence(run):
    state, model = run('<sql>SELECT count(*) AS n FROM transactions</sql>', '600 observations.')
    assert not state['failure']
    assert state['exec_result'].rows == [[600]]
    assert state['tables_used'] == ['transactions']
    assert state['sql'] == state['exec_result'].executed_sql
    assert model.calls == 2


def test_retry_repairs_unsafe_query(run):
    state, _ = run('<sql>SELECT * FROM mortgages</sql>', '<sql>SELECT count(*) FROM transactions</sql>', '600 observations.')
    assert not state['failure'] and state['attempts'] == 2


def test_unsupported_stops_without_execution(run):
    state, model = run('<unsupported>No lender records.</unsupported>')
    assert state['failure']['type'] == 'UNSUPPORTED'
    assert model.calls == 1 and state['exec_result'] is None


def test_dry_run_validates_without_execution(run):
    state, model = run('<sql>SELECT count(*) FROM transactions</sql>', dry_run=True)
    assert not state['failure'] and state['exec_result'] is None and model.calls == 1
