import pytest

from app.services.sql_validator import validate_product_query, product_tables_used
from app.core.prompt_builder import build_system_prompt, build_user_prompt, MAX_PROMPT_CHARS


@pytest.mark.parametrize('sql', [
    "SELECT sum(price_aed) FROM transactions WHERE transaction_date >= DATE '2025-01-01' AND transaction_date < DATE '2026-01-01'",
    "SELECT date_trunc('month', transaction_date),sum(price_aed) FROM bayan.transactions GROUP BY 1",
    'WITH sales AS (SELECT * FROM transactions) SELECT count(*) FROM sales',
    'SELECT * FROM transactions WHERE price_aed > (SELECT avg(price_aed) FROM transactions)',
    'SELECT district FROM transactions UNION SELECT municipality FROM price_indices',
    "SELECT SUM(price_aed)::numeric / NULLIF(COUNT(*), 0) FROM transactions",
])
def test_allows_supported_analytical_queries(sql):
    assert validate_product_query(sql).is_safe


@pytest.mark.parametrize('sql', [
    'SELECT * FROM mortgages', 'SELECT * FROM public.transactions',
    'SELECT * FROM adrec_intake.observations', 'SELECT * FROM pg_catalog.pg_class',
    'WITH transactions AS (SELECT * FROM brokers) SELECT * FROM transactions',
    'SELECT * FROM transactions WHERE EXISTS (SELECT 1 FROM developers)',
    'SELECT pg_sleep(1)', "SELECT set_config('search_path','public',true)",
    'SELECT public.sum(price_aed) FROM transactions',
    'SELECT * FROM generate_series(1,100000000)',
    'SELECT * FROM transactions FOR UPDATE',
    "SELECT 'transactions'::regclass", "SELECT 'x'::public.custom_type",
    'WITH RECURSIVE r AS (SELECT 1 UNION ALL SELECT 1 FROM r) SELECT * FROM r',
])
def test_rejects_nonproduct_access_and_unsafe_functions(sql):
    assert not validate_product_query(sql).is_safe


def test_resolves_cte_to_actual_relations():
    assert product_tables_used('WITH sales AS (SELECT * FROM transactions) SELECT * FROM sales') == ['transactions']


def test_fresh_prompt_uses_source_fields_without_legacy_hierarchy():
    prompt = build_system_prompt()
    assert 'community_id' not in prompt and 'name_ar' not in prompt
    assert 'active_value_aed is not annual rent' in prompt
    assert '5+ beds versus 6+ beds' in prompt
    assert '<unsupported>' in prompt
    user = build_user_prompt('q', 'x'*50000, system_prompt=prompt)
    assert len(prompt) + len(user) <= MAX_PROMPT_CHARS
