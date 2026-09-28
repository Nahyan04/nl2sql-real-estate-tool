from app.services.query_metadata import date_conditions


def test_extracts_only_executed_date_conditions():
    sql = """SELECT sum(price_aed) FROM transactions
        WHERE transaction_date >= DATE '2025-01-01'
        AND transaction_date < DATE '2026-01-01' AND price_aed > 0"""
    assert date_conditions(sql) == [
        "transaction_date >= CAST('2025-01-01' AS DATE)",
        "transaction_date < CAST('2026-01-01' AS DATE)",
    ]


def test_query_without_date_filter_has_no_conditions():
    assert date_conditions("SELECT count(*) FROM transactions") == []


def test_lease_date_in_join_is_evidence_but_column_join_is_not():
    sql = """SELECT count(*) FROM rental_observations r
        JOIN rental_observations u ON r.period_end = u.period_end
        AND u.period_end = DATE '2026-06-30'"""
    assert date_conditions(sql) == ["u.period_end = CAST('2026-06-30' AS DATE)"]


def test_lease_quarter_dates_in_in_predicate_are_evidence():
    sql = """SELECT SUM(active_value_aed) FROM rental_observations
        WHERE period_end IN (DATE '2026-03-31', DATE '2026-06-30')"""
    assert date_conditions(sql) == [
        "period_end IN (CAST('2026-03-31' AS DATE), CAST('2026-06-30' AS DATE))"
    ]
