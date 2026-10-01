from app.services.query_semantics import missing_question_filters


QUESTION = "For ready residential apartment sales in 2025 with sold area above 1 sqm, what was the average calculated AED per sqm?"
DATES = " AND transaction_date >= DATE '2025-01-01' AND transaction_date < DATE '2026-01-01'"
BASE = "SELECT AVG(calculated_rate_aed_sqm) FROM transactions WHERE sale_type = 'ready' AND property_type = 'apartment' AND sold_area_sqm > 1" + DATES


def test_requires_explicit_residential_filter():
    assert missing_question_filters(QUESTION, BASE) == ["asset_class = 'residential'"]
    assert missing_question_filters(QUESTION, BASE + " AND asset_class = 'residential'") == []


def test_or_predicates_do_not_satisfy_all_required_filters():
    sql = "SELECT AVG(calculated_rate_aed_sqm) FROM transactions WHERE sale_type = 'ready' OR asset_class = 'residential' OR property_type = 'apartment'"
    assert missing_question_filters(QUESTION, sql)


def test_requires_explicit_sold_area_threshold():
    sql = BASE.replace(" AND sold_area_sqm > 1", "") + " AND asset_class = 'residential'"
    assert missing_question_filters(QUESTION, sql) == ["sold_area_sqm > 1"]


def test_requires_year_boundaries_and_off_plan_filter():
    question = "How many off-plan sales observations were recorded in 2025?"
    sql = "SELECT COUNT(*) FROM transactions WHERE transaction_date >= DATE '2025-01-01' AND transaction_date < DATE '2026-01-01'"
    assert missing_question_filters(question, sql) == ["sale_type = 'off-plan'"]
    assert missing_question_filters(question, sql + " AND sale_type = 'off-plan'") == []
    assert "transaction_date >= DATE '2025-01-01'" in missing_question_filters(
        question, "SELECT COUNT(*) FROM transactions WHERE sale_type = 'off-plan'",
    )


def test_requires_fractional_share_bounds():
    question = "How many exported 2025 sales observations had a sold ownership share greater than zero and less than one?"
    sql = "SELECT COUNT(*) FROM transactions WHERE sold_share > 0" + DATES
    assert missing_question_filters(question, sql) == ["sold_share < 1"]
    assert missing_question_filters(question, sql + " AND sold_share < 1") == []


def test_other_questions_are_not_forced_into_this_scope():
    assert missing_question_filters("Compare ready and off-plan sales in 2025", BASE) == []
