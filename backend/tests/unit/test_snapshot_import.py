import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.genlib.snapshot_import import import_snapshot, source_records
from scripts.genlib.source_contract import ContractError


def test_production_target_rejected_before_any_io():
    with pytest.raises(ContractError, match='prefix'):
        import_snapshot(None, Path('/does/not/exist'), 'production')


def test_records_preserve_source_precision_duplicates_and_unresolved_geography():
    frame = pd.DataFrame([{'District': 'Al Bateen', 'Property Layout': '5+ beds', 'Property Sold Area (SQM)': '1.0000', 'Property Sold Share': '0.0009', 'Rate (AED per SQM)': '9717.0273350987522158'}] * 2)
    spec = {'numeric_columns':['Property Sold Area (SQM)', 'Property Sold Share', 'Rate (AED per SQM)']}
    records = list(source_records(frame, spec))
    assert [r['source_row'] for r in records] == [1, 2]
    assert json.loads(records[0]['metrics'])['Rate (AED per SQM)'] == '9717.0273350987522158'
    assert json.loads(records[0]['dimensions']) == {'District': 'Al Bateen', 'Property Layout': '5+ beds'}
    assert json.loads(records[0]['quality_flags']) == ['sold_area_at_or_below_one_sqm', 'municipality_not_provided']


def test_missing_values_remain_explicit():
    result = next(source_records(pd.DataFrame([{'District':'', 'Property Sold Area (SQM)': None}]), {'numeric_columns':['Property Sold Area (SQM)']}))
    assert json.loads(result['metrics']) == {'Property Sold Area (SQM)': None}
    assert json.loads(result['dimensions']) == {'District': None}
    assert 'missing_sold_area' in json.loads(result['quality_flags'])
