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


def test_explicit_ready_residential_scope_gets_repair_feedback(sqlite_engine, monkeypatch):
    monkeypatch.setattr(graph, 'introspect_product_schema', lambda _: introspect_schema(sqlite_engine))
    question = 'For ready residential apartment sales in 2025 with sold area above 1 sqm, what was the average calculated AED per sqm?'
    incomplete = "<sql>SELECT AVG(calculated_rate_aed_sqm) FROM transactions WHERE sale_type = 'ready' AND property_type = 'apartment' AND sold_area_sqm > 1 AND transaction_date >= DATE '2025-01-01' AND transaction_date < DATE '2026-01-01'</sql>"
    complete = "<sql>SELECT AVG(calculated_rate_aed_sqm) FROM transactions WHERE sale_type = 'ready' AND property_type = 'apartment' AND asset_class = 'residential' AND sold_area_sqm > 1 AND transaction_date >= DATE '2025-01-01' AND transaction_date < DATE '2026-01-01'</sql>"
    model = Model(incomplete, complete)
    state = run_pipeline(question, chat_model=model, engine=sqlite_engine,
                         engine_ro=sqlite_engine, dry_run=True)
    assert state['failure'] is None and state['attempts'] == 2
    assert "asset_class = 'residential'" in state['sql']


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
    state = run_pipeline('How many exported apartment sales observations in 2025?',
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
def test_source_clarification_avoids_model(sqlite_engine, monkeypatch, question):
    from app.services.question_context import Place
    schema = introspect_schema(sqlite_engine)
    schema['coverage'] = [{'source_file': 'Transactions/recent_sales.csv', 'observed_from': '2019-01-01', 'observed_through': '2026-07-31'}]
    monkeypatch.setattr(graph, 'introspect_product_schema', lambda _: schema)
    monkeypatch.setattr(graph, 'load_places', lambda *args, **kwargs: [Place('transactions', 'district', 'Al Bateen'), Place('transactions', 'community', 'Al Bateen')])
    model = Model('<sql>SELECT 1</sql>')
    state = run_pipeline(question, chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine)
    assert state['failure']['type'] == 'CLARIFICATION'
    assert state['attempts'] == 0 and model.calls == 0


def test_arabic_bateen_district_uses_validated_source_plan(sqlite_engine, monkeypatch):
    monkeypatch.setattr(graph, 'introspect_product_schema', lambda _: introspect_schema(sqlite_engine))
    model = Model('unneeded')
    state = run_pipeline('كم قيمة المبيعات في منطقه البطين عام 2025؟',
                         chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine,
                         dry_run=True)
    assert state['failure'] is None
    assert state['query_method'] == 'source_plan:sales_district_value'
    assert "district = 'Al Bateen'" in state['sql']
    assert state['language'] == 'ar'
    assert model.calls == 0


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


def source_context_fixture(sqlite_engine, monkeypatch, places=None):
    from app.services.question_context import Place
    schema = introspect_schema(sqlite_engine)
    schema['coverage'] = [{'source_file': 'Transactions/recent_sales.csv', 'observed_from': '2019-01-01', 'observed_through': '2026-07-31'}]
    monkeypatch.setattr(graph, 'introspect_product_schema', lambda _: schema)
    monkeypatch.setattr(graph, 'load_places', lambda *args, **kwargs: places or [Place('transactions', 'district', 'Khalifa City')])


def test_original_khalifa_question_offers_source_choice_then_generates(sqlite_engine, monkeypatch):
    from app.models.contracts import ClarificationAnswer
    source_context_fixture(sqlite_engine, monkeypatch)
    question = 'What is the average sale price of villas in khalifa city A in 2025?'
    model = Model('unused')
    state = run_pipeline(question, chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine, dry_run=True)
    assert state['failure']['type'] == 'CLARIFICATION' and model.calls == 0
    choice = state['clarification_questions'][0]
    answer = ClarificationAnswer(question_id=choice.id, option_id=choice.options[0].id)
    sql = "SELECT AVG(price_aed) AS average_sale_price_aed FROM transactions WHERE district = 'Khalifa City' AND property_type = 'villa' AND transaction_date >= DATE '2025-01-01' AND transaction_date < DATE '2026-01-01'"
    class CaptureModel(Model):
        def invoke(self, messages):
            self.messages = messages
            return super().invoke(messages)
    model = CaptureModel('<sql>' + sql + '</sql>')
    state = run_pipeline(question, chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine,
                         dry_run=True, clarification_answers=[answer])
    assert state['failure'] is None and state['query_method'] == 'model'
    assert state['sql'] == sql and state['resolved_scope'] == ['district: Khalifa City']
    assert 'Verified question context' in model.messages[0].content
    assert 'Khalifa City' in model.messages[0].content


def test_scope_omission_gets_repair_before_execution(sqlite_engine, monkeypatch):
    source_context_fixture(sqlite_engine, monkeypatch)
    model = Model('<sql>SELECT AVG(price_aed) FROM transactions</sql>',
                  "<sql>SELECT AVG(price_aed) FROM transactions WHERE district = 'Khalifa City'</sql>")
    state = run_pipeline('Average sale price in Khalifa City in 2025?', chat_model=model,
                         engine=sqlite_engine, engine_ro=sqlite_engine, dry_run=True)
    assert state['failure'] is None and model.calls == 2
    assert "district = 'Khalifa City'" in state['sql']


def test_two_clarifications_stop_after_unresolved_model_response(sqlite_engine, monkeypatch):
    from app.services.question_context import Place
    from app.models.contracts import ClarificationAnswer
    source_context_fixture(sqlite_engine, monkeypatch, [Place('transactions', 'district', 'Al Bateen'), Place('transactions', 'community', 'Al Bateen')])
    question = 'Show recent sales in Al Bateen'
    first = run_pipeline(question, chat_model=Model('unused'), engine=sqlite_engine, engine_ro=sqlite_engine, dry_run=True)
    answers = [ClarificationAnswer(question_id=q.id, option_id=q.options[0].id) for q in first['clarification_questions']]
    assert len(answers) == 2
    model = Model('<clarification>Which scope?</clarification>')
    final = run_pipeline(question, chat_model=model, engine=sqlite_engine, engine_ro=sqlite_engine,
                         dry_run=True, clarification_answers=answers)
    assert final['failure']['type'] == 'CLARIFICATION_EXHAUSTED'
    assert not final.get('clarification_questions') and model.calls == 1


def test_confirmed_place_with_no_data_terminates_cleanly(sqlite_engine, monkeypatch):
    from app.services.executor import ExecResult
    source_context_fixture(sqlite_engine, monkeypatch)
    monkeypatch.setattr(graph, 'execute_readonly', lambda *a, **kw: ExecResult(
        columns=['average_sale_price_aed'], rows=[[None]], row_count=1,
        executed_sql="SELECT AVG(price_aed) AS average_sale_price_aed FROM transactions WHERE district = 'Khalifa City'"))
    model = Model("<sql>SELECT AVG(price_aed) AS average_sale_price_aed FROM transactions WHERE district = 'Khalifa City'</sql>")
    state = run_pipeline('Average sale price in Khalifa City in 2030?', chat_model=model,
                         engine=sqlite_engine, engine_ro=sqlite_engine)
    assert state['outcome'] == 'no_data' and state['failure'] is None
    assert state['chart'] is None and model.calls == 1
