from app.services.query_semantics import missing_question_filters


QUESTION = "For ready residential apartment sales in 2025 with sold area above 1 sqm, what was the average calculated AED per sqm?"
BASE = "SELECT AVG(calculated_rate_aed_sqm) FROM transactions WHERE sale_type = 'ready' AND property_type = 'apartment' AND sold_area_sqm > 1"


def test_requires_explicit_residential_filter():
    assert missing_question_filters(QUESTION, BASE) == ["asset_class = 'residential'"]
    assert missing_question_filters(QUESTION, BASE + " AND asset_class = 'residential'") == []


def test_or_predicates_do_not_satisfy_all_required_filters():
    sql = "SELECT AVG(calculated_rate_aed_sqm) FROM transactions WHERE sale_type = 'ready' OR asset_class = 'residential' OR property_type = 'apartment'"
    assert missing_question_filters(QUESTION, sql)


def test_requires_explicit_sold_area_threshold():
    sql = BASE.replace(" AND sold_area_sqm > 1", "") + " AND asset_class = 'residential'"
    assert missing_question_filters(QUESTION, sql) == ["sold_area_sqm > 1"]


def test_other_questions_are_not_forced_into_this_scope():
    assert missing_question_filters("Compare ready and off-plan sales in 2025", BASE) == []
