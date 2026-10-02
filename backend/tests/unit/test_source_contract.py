import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.genlib.source_contract import CONTRACT, ContractError, lease_reconciliation, read_source, review_items, validate_frame


def spec():
    return {'columns': ['Date', 'Property Layout', 'Value'], 'categories': {'Property Layout': ['5+ beds', '6+ beds']}, 'numeric_columns': ['Value'], 'date_columns': ['Date']}


def frame():
    return pd.DataFrame([['2026-06-30', '5+ beds', 0.25], ['2026-06-30', '6+ beds', 1]], columns=spec()['columns'])


def test_preserves_distinct_layouts_fractional_values_and_duplicate_rows():
    data = pd.concat([frame(), frame()])
    before = data.copy(deep=True)
    validate_frame(data, spec())
    pd.testing.assert_frame_equal(data, before)


@pytest.mark.parametrize('change', ['columns', 'category', 'numeric', 'date'])
def test_schema_drift_is_rejected(change):
    data = frame()
    if change == 'columns':
        data = data.rename(columns={'Value': 'New Value'})
    else:
        column, value = {'category': ('Property Layout', '7 beds'), 'numeric': ('Value', 'unknown'), 'date': ('Date', 'invalid')}[change]
        data[column] = data[column].astype(object)
        data.loc[0, column] = value
    with pytest.raises(ContractError):
        validate_frame(data, spec())


def test_short_csv_record_is_rejected(tmp_path):
    path = tmp_path / 'sales.csv'
    path.write_text('Date,Property Layout,Value\n2026-06-30,5+ beds\n')
    with pytest.raises(ContractError, match='width'):
        read_source(path, spec())


def test_null_and_unmatched_lease_keys_are_accounted_for():
    key = ['Date', 'Property Type', 'Municipality', 'District', 'Property Layout']
    units = pd.DataFrame([['2026-06-30', 'apartment', 'A', None, '5+ beds', 2], ['2026-06-30', 'villa', 'A', 'X', '6+ beds', 1]], columns=key + ['Leased Units'])
    values = pd.DataFrame([['2026-06-30', 'apartment', 'A', None, '5+ beds', 503]], columns=key + ['Sum of active_value_aed'])
    result = lease_reconciliation(units, values)
    assert result['join_counts'] == {'both': 1, 'left_only': 1, 'right_only': 0}
    assert result['units_null_key_rows'] == 1
    assert not result['derived_annual_rent_supported']


def test_reconciliation_findings_are_advisory():
    report = {'lease_join': {'join_counts': {'left_only': 2, 'right_only': 1}},
              'ambiguous_districts': {'Al Bateen': ['Abu Dhabi City', 'Al Dhafra Region']},
              'transaction_area_flags': {'at_or_below_one_sqm': 3},
              'sources': {'source.xlsx': {'duplicate_keys_after_first': 2}},
              'financing_arithmetic': {'finance.xlsx': {'nonzero_delta_rows': 4}}}
    assert review_items(report) == [
        {'code': 'unmatched_lease_keys', 'count': 3},
        {'code': 'ambiguous_districts', 'count': 1},
        {'code': 'small_sold_areas', 'count': 3},
        {'code': 'duplicate_candidate_keys', 'source_file': 'source.xlsx', 'count': 2},
        {'code': 'financing_arithmetic', 'source_file': 'finance.xlsx', 'count': 4},
    ]


def test_contract_keeps_all_31_sources_and_index_dimensions():
    sources = json.loads(CONTRACT.read_text())['sources']
    assert len(sources) == 31
    for name, source in sources.items():
        if 'price_index' in name:
            assert {'Municipality', 'App Type', 'Property Type'} <= set(source['candidate_key'])
    sales = sources['Transactions/recent_sales_2019-2026.csv']
    assert sales['candidate_key'] == []
    assert 'Property Sold Share' in sales['numeric_columns']
