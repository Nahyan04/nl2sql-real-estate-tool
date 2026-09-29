from app.services.rental_query_plans import source_rental_plan, render_rental_plan_answer
from app.services.sql_validator import validate_product_query


def test_net_and_individual_wording_uses_same_gross_segment_plan():
    plan = source_rental_plan('What is the net rental yield for an individual Al Reem Island apartment in Q2 2026?')
    assert plan and plan.kind == 'gross_segment_yield'
    assert "DATE '2026-06-30'" in plan.sql
    assert "c.district = 'Al Reem Island'" in plan.sql
    assert "c.property_type = 'apartment'" in plan.sql
    assert 'matched_units_count' in plan.sql
    assert validate_product_query(plan.sql).is_safe


def test_weighted_rent_plan_keeps_matching_source_grain():
    plan = source_rental_plan('For Al Reem Island apartments in Q2 2026, what is the leased-unit-weighted annual rent estimate?')
    assert plan and plan.kind == 'weighted_annual_rent'
    assert 'c.layout = u.layout' in plan.sql
    assert 'SUM(source_annual_rent * unit_count)' in plan.sql
    assert validate_product_query(plan.sql).is_safe


def test_layout_wording_filters_the_requested_segment():
    for wording in ("1 bedroom", "one-bedroom", "1 bed"):
        plan = source_rental_plan(f"What is the rental yield for Al Reem Island {wording} apartments in Q2 2026?")
        assert plan and "c.layout = '1 bed'" in plan.sql
    assert source_rental_plan("What is the rental yield for Al Reem Island many-bedroom apartments in Q2 2026?") is None


def test_rent_index_plan_selects_one_source_series():
    plan = source_rental_plan('What was the percentage change from June 2025 to June 2026 in the Abu Dhabi City all-rents index for all residential property types and all zones?')
    assert plan and plan.kind == 'rent_index_change'
    assert "old.application_type = '(all rents)'" in plan.sql
    assert "DATE '2025-06-30'" in plan.sql and "DATE '2026-06-30'" in plan.sql
    assert validate_product_query(plan.sql).is_safe


def test_arabic_index_and_yield_phrasings():
    index = source_rental_plan('ما نسبة التغير من يونيو 2025 إلى يونيو 2026 في مؤشر جميع الإيجارات لجميع أنواع العقارات السكنية وجميع المناطق في مدينة أبوظبي؟')
    yield_plan = source_rental_plan('ما صافي العائد الإيجاري لشقة في Al Reem Island في الربع الثاني 2026؟')
    assert index and index.kind == 'rent_index_change'
    assert yield_plan and yield_plan.kind == 'gross_segment_yield'


def test_missing_period_or_area_does_not_guess_a_plan():
    assert source_rental_plan('What is the net yield for an apartment this year?') is None
    assert source_rental_plan('What is the rent index in Abu Dhabi?') is None


def test_residential_leased_units_use_quarter_end_source():
    plan = source_rental_plan('How many source-labelled residential leased units were recorded at the end of Q2 2026?')
    assert plan and plan.kind == 'leased_units'
    assert "source_file = 'Residential Leases/lease_residential.xlsx'" in plan.sql
    assert "period_end = DATE '2026-06-30'" in plan.sql
    assert validate_product_query(plan.sql).is_safe
    assert '228,456' in render_rental_plan_answer(
        'How many residential leased units at the end of Q2 2026?', 'leased_units', [[228456]],
    )
    arabic = source_rental_plan("كم عدد الوحدات السكنية المؤجرة المسجلة في نهاية الربع الثاني من عام 2026 حسب المصدر؟")
    assert arabic and arabic.kind == "leased_units"
    assert "period_end = DATE '2026-06-30'" in arabic.sql
    assert "الربع الثاني" in render_rental_plan_answer(
        "كم عدد الوحدات السكنية المؤجرة المسجلة في نهاية الربع الثاني من عام 2026 حسب المصدر؟",
        "leased_units", [[228456]],
    )


def test_plan_answer_keeps_gross_and_net_distinct_in_requested_language():
    question = 'What is the net rental yield for an individual Al Reem Island apartment in Q2 2026?'
    answer = render_rental_plan_answer(question, 'gross_segment_yield', [[5.950492, 18951, 6]])
    assert '5.95%' in answer and '18,951' in answer
    assert 'gross segment' in answer and 'A net yield' in answer
    arabic = render_rental_plan_answer('ما صافي العائد لشقة في Al Reem Island في الربع الثاني 2026؟',
                                       'gross_segment_yield', [[5.950492, 18951, 6]])
    assert '5.95%' in arabic and 'صافي' in arabic and 'الإجمالي' in arabic


def test_arabic_index_answer_names_the_source_series():
    question = 'ما نسبة التغير من يونيو 2025 إلى يونيو 2026 في مؤشر جميع الإيجارات لجميع أنواع العقارات السكنية وجميع المناطق في مدينة أبوظبي؟'
    answer = render_rental_plan_answer(question, 'rent_index_change', [[9.2613249]])
    assert '9.26%' in answer and 'جميع الإيجارات' in answer


def test_quarterly_lease_value_plans_preserve_source_and_periods():
    cases = [
        ("What was the source-labelled residential lease value for Q1 2026 in AED?", ["2026-03-31"]),
        ("What was the sum of source-labelled residential lease value for Q1 and Q2 2026, in AED?", ["2026-03-31", "2026-06-30"]),
        ("ما مجموع قيمة الإيجارات السكنية الواردة في المصدر للربعين الأول والثاني من 2026 بالدرهم؟", ["2026-03-31", "2026-06-30"]),
    ]
    for question, expected_dates in cases:
        plan = source_rental_plan(question)
        assert plan and plan.kind == "residential_lease_value"
        assert "source_file = 'Residential Leases/lease_price_by_period.xlsx'" in plan.sql
        assert all(date in plan.sql for date in expected_dates)
        assert validate_product_query(plan.sql).is_safe
    assert source_rental_plan("What is the annual rent for an apartment in Q1 2026?") is None
    assert source_rental_plan("What was the source-labelled residential lease value for Q1 2026 in Al Reem Island?") is None
    arabic_answer = render_rental_plan_answer(cases[2][0], "residential_lease_value", [[9324978842]])
    assert "الربع الأول من 2026 والربع الثاني من 2026" in arabic_answer
    assert "Q1" not in arabic_answer


def test_index_level_uses_exact_source_values_and_unit():
    question = "What was the June 2026 Abu Dhabi City all-rents residential index level for all zones and property types?"
    plan = source_rental_plan(question)
    assert plan and plan.kind == "rent_index_level"
    assert "index_type = 'rent'" in plan.sql
    assert "application_type = '(all rents)'" in plan.sql
    assert "period_end = DATE '2026-06-30'" in plan.sql
    assert validate_product_query(plan.sql).is_safe
    assert "107.2578" in render_rental_plan_answer(question, plan.kind, [[107.2578]])


def test_one_bedroom_answer_names_layout():
    answer = render_rental_plan_answer(
        "What was the indicative gross segment yield for one-bedroom Al Reem Island apartments in Q2 2026?",
        "gross_segment_yield", [[5.950492, 123, 1]],
    )
    assert "1-bedroom" in answer and "1 matched layout" in answer


def test_reem_layout_yield_ranking_uses_comparison_export():
    question = "Which Al Reem Island apartment layouts had the highest indicative gross segment yields in Q2 2026?"
    plan = source_rental_plan(question)
    assert plan and plan.kind == "gross_segment_yield_ranking"
    assert "Price Indices/average_sale_rent_prices_by_product_area.xlsx" in plan.sql
    assert "period_end = DATE '2026-06-30'" in plan.sql
    assert "ORDER BY gross_segment_yield_pct DESC" in plan.sql
    assert validate_product_query(plan.sql).is_safe
    answer = render_rental_plan_answer(question, plan.kind, [["2 beds", 6.5], ["1 bed", 6.2]])
    assert "indicative gross segment yield" in answer and "2 beds (6.50%)" in answer
    assert source_rental_plan(question.replace("Al Reem Island", "Yas Island")) is None
