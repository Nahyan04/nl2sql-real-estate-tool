from app.services.answer_synthesizer import synthesize_answer
from app.services.executor import ExecResult
from app.core.language import answer_matches_language, resolve_language
from app.services.sales_query_plans import render_sales_district_value, sales_district_value_plan
from langchain_core.messages import AIMessage
import pytest


def test_language_choice_overrides_prompt_script():
    assert resolve_language('كم قيمة المبيعات؟', 'en') == 'en'
    assert resolve_language('How many sales?', 'ar') == 'ar'
    assert resolve_language('كم قيمة المبيعات؟') == 'ar'
    assert not answer_matches_language('بلغ الإجمالي 4 مليون درهم. The total was AED 4 million.', 'ar')
    assert answer_matches_language('بلغت المبيعات في Al Bateen نحو 4 ملايين درهم.', 'ar', ('Al Bateen',))


def test_wrong_language_answer_is_repaired_once():
    responses = iter(['The total is AED 4 million.', 'بلغ الإجمالي 4 مليون درهم.'])
    calls = []
    def invoke(messages):
        calls.append(messages)
        return AIMessage(content=next(responses))
    result = ExecResult(columns=['total_aed'], rows=[[4_000_000]], row_count=1)
    answer = synthesize_answer('كم الإجمالي؟', 'SELECT 4000000 AS total_aed', result, invoke)
    assert answer == 'بلغ الإجمالي 4 مليون درهم.'
    assert len(calls) == 2


def test_language_repair_cannot_change_figures():
    responses = iter(['The total is AED 4 million.', 'بلغ الإجمالي 5 مليون درهم.'])
    result = ExecResult(columns=['total_aed'], rows=[[4_000_000]], row_count=1)
    with pytest.raises(ValueError, match='figures changed'):
        synthesize_answer('كم الإجمالي؟', 'SELECT 4000000 AS total_aed', result,
                          lambda _: AIMessage(content=next(responses)))


def test_bateen_plan_keeps_source_district_and_year():
    plan = sales_district_value_plan('كم قيمة المبيعات في منطقه البطين عام 2025؟')
    assert plan is not None
    assert "district = 'Al Bateen'" in plan[0]
    assert "DATE '2026-01-01'" in plan[0]
    answer = render_sales_district_value([[2000000, 2]], plan[1], 'ar')
    assert '2,000,000.00 درهم' in answer
    assert 'لا يحدد مصدر المبيعات البلدية' in answer
    assert sales_district_value_plan('كم عدد مبيعات منطقة البطين عام 2025؟') is None
