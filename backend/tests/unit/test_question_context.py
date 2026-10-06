from datetime import date

import pytest

from app.models.contracts import ClarificationAnswer, QueryRequest
from app.services.question_context import Place, QuestionContext, load_places, normalize, resolve_context
from app.services.query_semantics import missing_resolved_filters
from app.services.sql_validator import validate_product_query

COVERAGE = [{'source_file': 'Transactions/recent_sales.csv', 'observed_from': '2019-01-02',
             'observed_through': '2026-07-31', 'complete_through': None}]
PLACES = [Place('transactions', 'district', 'Khalifa City'),
          Place('transactions', 'district', 'Al Bateen'),
          Place('transactions', 'community', 'Al Bateen'),
          Place('transactions', 'district', 'Al Reem Island')]


def resolve(q, answers=None, **kwargs):
    return resolve_context(q, PLACES, COVERAGE, 'en', answers, **kwargs)


@pytest.mark.parametrize('place', ['khalifa CITY', 'KHALIFA-CITY', 'Khalifa City district', 'district of Khalifa City'])
def test_unique_source_match_needs_no_municipality_or_suffix(place):
    context = resolve(f'Average villa sale price in {place} in 2025?')
    assert context.places == PLACES[:1]
    assert not context.questions
    assert 'Khalifa City' in context.prompt()
    assert 'municipality' not in context.descriptions[0]


def test_a_suffix_is_not_silently_discarded_as_an_alias():
    context = resolve('What is the average sale price of villas in khalifa city A in 2025?')
    assert not context.places
    assert context.questions[0].prompt == 'Did you mean this place?'
    assert any(o.label == 'Khalifa City · district' for o in context.questions[0].options)


def test_typos_suggest_only_source_values_and_selected_choice_is_verified():
    question = 'Average villa sales in Khalifa Cti in 2025?'
    context = resolve(question)
    clarification = context.questions[0]
    chosen = clarification.options[0]
    answer = ClarificationAnswer(question_id=clarification.id, option_id=chosen.id)
    confirmed = resolve(question, [answer])
    assert confirmed.places[0].value == 'Khalifa City'
    assert not confirmed.invalid and not confirmed.questions
    assert resolve(question, [ClarificationAnswer(question_id=clarification.id, option_id='made-up')]).invalid
    assert resolve('Sales in Al Bateen in 2025?', [answer]).invalid


def test_high_confidence_single_typo_can_resolve_without_question():
    context = resolve('Average sale price in Khalifa Citty in 2025?')
    assert context.places == PLACES[:1] and not context.questions


def test_duplicate_place_levels_require_choice_but_explicit_level_does_not():
    ambiguous = resolve('Sales in Al Bateen in 2025?')
    assert not ambiguous.places and len(ambiguous.questions[0].options) == 3
    assert resolve('Sales in Al Bateen district in 2025?').places == [PLACES[1]]
    assert resolve('Sales in Al Bateen community in 2025?').places == [PLACES[2]]
    assert resolve('Sales in Al Bateen district in Abu Dhabi in 2025?').places == [PLACES[1]]


def test_arabic_verified_district_and_arabic_digits():
    assert normalize('عام ٢٠٢٥') == 'عام 2025'
    context = resolve_context('كم قيمة المبيعات في منطقة البطين عام ٢٠٢٥؟', PLACES, COVERAGE, 'ar')
    assert context.places == [PLACES[1]] and not context.questions


def test_explicit_year_wins_over_incidental_recent_word():
    context = resolve('Recent villa sales in Khalifa City in 2025?')
    assert not context.questions and context.period is None


@pytest.mark.parametrize(('wording', 'start', 'end'), [
    ('this year', '2026-01-01', '2026-10-07'),
    ('last year', '2025-01-01', '2026-01-01'),
    ('past 3 months', '2026-07-06', '2026-10-07'),
    ('past 30 days', '2026-09-07', '2026-10-07'),
    ('past 1 year', '2025-10-06', '2026-10-07'),
])
def test_calendar_relative_period_is_explicit_and_never_shifted_to_coverage(wording, start, end):
    context = resolve(f'Show sales {wording}', today=date(2026, 10, 6))
    assert context.period == (date.fromisoformat(start), date.fromisoformat(end))
    assert not context.questions


def test_month_end_relative_window_is_valid():
    context = resolve('Sales past 1 month', today=date(2026, 3, 31))
    assert context.period[0] == date(2026, 2, 28)


def test_latest_and_recent_offer_coverage_periods_without_claiming_completeness():
    context = resolve('Show recent sales in Al Bateen')
    assert len(context.questions) == 2
    place, period = context.questions
    assert '2026-07' in period.options[0].label
    answers = [ClarificationAnswer(question_id=q.id, option_id=q.options[0].id) for q in context.questions]
    confirmed = resolve('Show recent sales in Al Bateen', answers)
    assert not confirmed.questions and not confirmed.invalid
    assert confirmed.period == (date(2026, 7, 1), date(2026, 8, 1))
    assert not any('complete' in o.label.lower() for o in period.options)


def test_changed_snapshot_periods_and_none_choice_fail_closed():
    context = resolve('Latest sales?')
    answer = ClarificationAnswer(question_id='period', option_id=context.questions[0].options[0].id)
    newer = [dict(COVERAGE[0], observed_through='2026-08-31')]
    assert resolve_context('Latest sales?', PLACES, newer, 'en', [answer]).invalid
    context = resolve('Sales in Al Bateen in 2025?')
    assert resolve('Sales in Al Bateen in 2025?', [ClarificationAnswer(question_id=context.questions[0].id, option_id='none')]).invalid


def test_duplicate_and_excess_answers_are_rejected():
    answer = ClarificationAnswer(question_id='period', option_id='example')
    assert resolve('Latest sales?', [answer, answer]).invalid
    with pytest.raises(ValueError):
        QueryRequest(question='sales', clarification_answers=[answer] * 3)


def test_suggestion_uses_only_relevant_relation():
    places = [Place('rental_observations', 'district', 'Khalifa City')]
    assert not resolve_context('Sales in Khalifa City in 2025?', places, COVERAGE, 'en').places


@pytest.mark.parametrize('sql', [
    "SELECT AVG(price_aed) FROM transactions WHERE district = 'Khalifa City'",
    "SELECT AVG(t.price_aed) FROM transactions t WHERE (t.district = 'Khalifa City') AND t.property_type = 'villa'",
])
def test_confirmed_scope_allows_validated_filters(sql):
    assert validate_product_query(sql).is_safe
    assert missing_resolved_filters(sql, QuestionContext(places=PLACES[:1])) == []


@pytest.mark.parametrize('sql', [
    'SELECT AVG(price_aed) FROM transactions',
    "SELECT AVG(price_aed) FROM transactions WHERE community = 'Khalifa City'",
    "SELECT AVG(price_aed) FROM transactions WHERE district = 'Khalifa City' OR property_type = 'villa'",
])
def test_confirmed_scope_cannot_be_omitted_or_broadened(sql):
    assert missing_resolved_filters(sql, QuestionContext(places=PLACES[:1]))


def test_relative_period_must_be_preserved():
    context = resolve('Sales this year', today=date(2026, 10, 6))
    assert len(missing_resolved_filters('SELECT count(*) FROM transactions', context)) == 2
    sql = "SELECT count(*) FROM transactions WHERE transaction_date >= DATE '2026-01-01' AND transaction_date < DATE '2026-10-07'"
    assert not missing_resolved_filters(sql, context)


def test_catalog_is_readonly_bounded_and_refreshes_with_snapshot(monkeypatch, sqlite_engine):
    from app.services import question_context as module
    from app.services.executor import ExecResult
    calls = []
    def read(engine, sql, **kwargs):
        calls.append((sql, kwargs))
        assert validate_product_query(sql).is_safe
        return ExecResult(rows=[['transactions', 'district', 'Khalifa City']], row_count=1)
    monkeypatch.setattr(module, 'execute_readonly', read)
    schema = {'snapshot_id': 'a', 'tables': [{'name': 'transactions', 'columns': [{'name': 'district'}]}]}
    assert load_places(sqlite_engine, schema) == PLACES[:1]
    load_places(sqlite_engine, schema)
    assert len(calls) == 1 and calls[0][1]['limit'] == 10000
    load_places(sqlite_engine, dict(schema, snapshot_id='b'))
    assert len(calls) == 2
    monkeypatch.setattr(module, 'execute_readonly', lambda *a, **kw: ExecResult(truncated=True))
    with pytest.raises(ValueError):
        load_places(sqlite_engine, dict(schema, snapshot_id='c'))


def test_model_requested_missing_period_can_be_confirmed_on_next_request():
    first = resolve('Average sales?', ask_period=True)
    choice = first.questions[0]
    answer = ClarificationAnswer(question_id=choice.id, option_id=choice.options[0].id)
    next_request = resolve('Average sales?', [answer])
    assert next_request.period == (date(2026, 7, 1), date(2026, 8, 1))
    assert not next_request.invalid and not next_request.questions


def test_index_missing_municipality_offers_verified_choices_only():
    places = [Place('price_indices', 'municipality', value) for value in ['Abu Dhabi City', 'Al Ain City', 'Al Dhafra']]
    first = resolve_context('Rent index in 2025?', places, [], 'en')
    assert len(first.questions) == 1
    choice = first.questions[0]
    assert len(choice.options) == 3
    assert {o.label for o in choice.options} == {p.value for p in places}
    confirmed = resolve_context('Rent index in 2025?', places, [], 'en',
        [ClarificationAnswer(question_id=choice.id, option_id=choice.options[0].id)])
    assert not confirmed.questions and not confirmed.invalid
    explicit = resolve_context('Rent index for Abu Dhabi City in 2025?', places, [], 'en')
    assert not explicit.questions


def test_explicit_unsupported_place_level_cannot_silently_become_district():
    context = resolve('Sales in Khalifa City community in 2025?')
    assert not context.places
    assert context.questions and 'district' in context.questions[0].options[0].label


def test_multiple_places_support_exact_comparison_set_without_extra_area():
    context = resolve('Compare Khalifa City and Al Reem Island sales in 2025?')
    assert len(context.places) == 2
    sql = "SELECT district, AVG(price_aed) FROM transactions WHERE district IN ('Khalifa City', 'Al Reem Island') GROUP BY district"
    assert not missing_resolved_filters(sql, context)
    broader = sql.replace("'Al Reem Island')", "'Al Reem Island', 'Al Bateen')")
    assert missing_resolved_filters(broader, context)


@pytest.mark.parametrize('question', ['Sales in 2025 excluding Khalifa City?', 'Which districts have prices higher than Khalifa City in 2025?'])
def test_exclusions_and_benchmarks_do_not_gain_positive_place_filters(question):
    context = resolve(question)
    assert not context.places and context.references == PLACES[:1]
    assert not missing_resolved_filters("SELECT district FROM transactions WHERE district != 'Khalifa City'", context)
    assert 'place_references' in context.prompt()
