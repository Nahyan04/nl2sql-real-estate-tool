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
