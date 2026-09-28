import pytest
from langchain_core.messages import AIMessage
from app.config import Settings
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


class FailingModel:
    def invoke(self, messages):
        raise ConnectionError('internal-provider-url:secret')


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


def test_pipeline_records_model_usage_for_evaluation(sqlite_engine, monkeypatch):
    monkeypatch.setattr(graph, 'introspect_product_schema', lambda _: introspect_schema(sqlite_engine))
    class UsageModel:
        def __init__(self):
            self.calls = 0

        def invoke(self, messages):
            self.calls += 1
            content = '<sql>SELECT count(*) AS observation_count FROM transactions</sql>' if self.calls == 1 else '600 observations.'
            return AIMessage(content=content,
                             usage_metadata={'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120},
                             response_metadata={'model_name': 'claude-haiku-4-5-20251001'})

    state = run_pipeline('sales count', chat_model=UsageModel(), engine=sqlite_engine, engine_ro=sqlite_engine)
    assert state['model_usage'] == {
        'calls': 2, 'input_tokens': 200, 'output_tokens': 40,
        'model': 'claude-haiku-4-5-20251001',
    }


def test_retry_repairs_unsafe_query(run):
    state, _ = run('<sql>SELECT * FROM mortgages</sql>', '<sql>SELECT count(*) FROM transactions</sql>', '600 observations.')
    assert not state['failure'] and state['attempts'] == 2


def test_unsupported_stops_without_execution(run):
    state, model = run('<unsupported>No lender records.</unsupported>')
    assert state['failure']['type'] == 'UNSUPPORTED'
    assert model.calls == 1 and state['exec_result'] is None


def test_model_clarification_stops_without_retry(run):
    state, model = run('<clarification>Which period?</clarification>')
    assert state['failure']['type'] == 'CLARIFICATION'
    assert model.calls == 1 and state['exec_result'] is None


def test_explicit_year_gets_one_recovery_attempt(sqlite_engine, monkeypatch):
    monkeypatch.setattr(graph, 'introspect_product_schema', lambda _: introspect_schema(sqlite_engine))
    model = Model('<clarification>Which year?</clarification>',
                  '<sql>SELECT count(*) AS observation_count FROM transactions</sql>')
    state = run_pipeline('How many exported sales observations in 2025?',
                         chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine,
                         dry_run=True)
    assert state['failure'] is None
    assert state['attempts'] == 2 and model.calls == 2


def test_empty_result_has_explicit_outcome_without_synthesis(run):
    state, model = run('<sql>SELECT id FROM transactions WHERE id < 0</sql>')
    assert state['failure'] is None
    assert state['outcome'] == 'no_data'
    assert state['answer'] == 'No matching data was returned for this question.'
    assert model.calls == 1


def test_zero_count_is_a_valid_answer(run):
    state, model = run('<sql>SELECT count(*) AS observation_count FROM transactions WHERE id < 0</sql>', 'Zero observations.')
    assert state['outcome'] == 'answer'
    assert state['exec_result'].rows == [[0]]
    assert model.calls == 2


def test_generation_provider_failure_is_explicit(sqlite_engine, monkeypatch):
    monkeypatch.setattr(graph, 'introspect_product_schema', lambda _: introspect_schema(sqlite_engine))
    state = run_pipeline('sales count', chat_model=FailingModel(), engine=sqlite_engine, engine_ro=sqlite_engine)
    assert state['failure']['type'] == 'PROVIDER_UNAVAILABLE'
    assert state['attempts'] == 1


def test_synthesis_provider_failure_is_explicit(sqlite_engine, monkeypatch):
    monkeypatch.setattr(graph, 'introspect_product_schema', lambda _: introspect_schema(sqlite_engine))
    class FirstCallModel:
        calls = 0
        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(content='<sql>SELECT count(*) AS observation_count FROM transactions</sql>')
            raise ConnectionError('internal-provider-url:secret')
    state = run_pipeline('sales count', chat_model=FirstCallModel(), engine=sqlite_engine, engine_ro=sqlite_engine)
    assert state['failure']['type'] == 'PROVIDER_UNAVAILABLE'
    assert state['exec_result'].rows == [[600]]


@pytest.mark.parametrize('question', ['What were the latest sales?', 'كم بلغت مبيعات البطين في 2025؟'])
def test_clarification_preflight_avoids_model_and_database(question):
    model = Model('<sql>SELECT 1</sql>')
    state = run_pipeline(question, chat_model=model,
                         settings=Settings(database_url='postgresql://unused/unused', readonly_db_password='unused'))
    assert state['failure']['type'] == 'CLARIFICATION'
    assert state['attempts'] == 0 and model.calls == 0


@pytest.mark.parametrize('question', ['What is the rental yield?', 'ما العائد الإيجاري؟'])
def test_gross_segment_yield_can_reach_query_generation(sqlite_engine, monkeypatch, question):
    monkeypatch.setattr(graph, 'introspect_product_schema', lambda _: introspect_schema(sqlite_engine))
    model = Model("<sql>SELECT 100 * source_annual_rent / NULLIF(source_average_sale_price_aed, 0) AS gross_yield_proxy_pct FROM rental_observations WHERE source_file = 'Price Indices/average_sale_rent_prices_by_product_area.xlsx' AND period_end = DATE '2026-06-30' AND source_annual_rent > 0 AND source_average_sale_price_aed > 0</sql>")
    state = run_pipeline(question, chat_model=model, engine=sqlite_engine,
                         engine_ro=sqlite_engine, dry_run=True)
    assert state['failure'] is None
    assert state['attempts'] == 1 and model.calls == 1


@pytest.mark.parametrize('question', [
    'What is the net rental yield for an individual Al Reem Island apartment in Q2 2026?',
    'ما صافي العائد الإيجاري لشقة في Al Reem Island في الربع الثاني 2026؟',
])
def test_source_answerable_yield_uses_validated_plan(sqlite_engine, monkeypatch, question):
    monkeypatch.setattr(graph, 'introspect_product_schema', lambda _: introspect_schema(sqlite_engine))
    model = Model('<unsupported>Missing costs</unsupported>')
    state = run_pipeline(question, chat_model=model, engine=sqlite_engine,
                         engine_ro=sqlite_engine, dry_run=True)
    assert state['failure'] is None
    assert state['query_method'] == 'source_plan:gross_segment_yield'
    assert state['attempts'] == 0 and model.calls == 0


def test_dry_run_validates_without_execution(run):
    state, model = run('<sql>SELECT count(*) FROM transactions</sql>', dry_run=True)
    assert not state['failure'] and state['exec_result'] is None and model.calls == 1


def test_generation_attempt_limit_is_configurable(sqlite_engine, monkeypatch):
    monkeypatch.setattr(
        graph, 'introspect_product_schema', lambda _: introspect_schema(sqlite_engine)
    )
    model = Model(
        '<sql>SELECT * FROM mortgages</sql>',
        '<sql>SELECT count(*) FROM transactions</sql>',
    )
    settings = Settings(model_generation_attempts=1)

    state = run_pipeline(
        'sales count',
        chat_model=model,
        engine=sqlite_engine,
        engine_ro=sqlite_engine,
        settings=settings,
    )

    assert state['failure']['type'] == 'UNSAFE_SQL'
    assert state['attempts'] == 1
    assert model.calls == 1


def test_expired_total_deadline_stops_before_model_call(sqlite_engine, monkeypatch):
    monkeypatch.setattr(
        graph, 'introspect_product_schema', lambda _: introspect_schema(sqlite_engine)
    )
    model = Model('<sql>SELECT count(*) FROM transactions</sql>')
    settings = Settings(request_timeout_s=0.000001)

    state = run_pipeline(
        'sales count',
        chat_model=model,
        engine=sqlite_engine,
        engine_ro=sqlite_engine,
        settings=settings,
    )

    assert state['failure']['type'] == 'REQUEST_TIMEOUT'
    assert model.calls == 0
