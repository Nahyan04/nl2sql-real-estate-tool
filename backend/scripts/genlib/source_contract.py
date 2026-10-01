"""Lossless native-export intake; never connects to the application database."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

CONTRACT = Path(__file__).resolve().parents[2] / 'app/resources/adrec_source_contract.json'


class ContractError(ValueError):
    pass


def validate_frame(frame: pd.DataFrame, spec: dict) -> None:
    if list(frame.columns) != spec['columns']:
        raise ContractError('Source columns/order changed; review the contract before importing')
    for column, allowed in spec['categories'].items():
        unknown = set(frame[column].dropna().astype(str)) - set(allowed) - {''}
        if unknown:
            raise ContractError(f'Unknown categories in {column}: {sorted(unknown)}')
    for column in spec['numeric_columns']:
        values = frame[column].replace('', None)
        converted = pd.to_numeric(values, errors='coerce')
        if (values.notna() & converted.isna()).any() or converted.isin([float('inf'), -float('inf')]).any():
            raise ContractError(f'Invalid numeric values in {column}')
    for column in spec['date_columns']:
        if pd.to_datetime(frame[column], errors='coerce').isna().any():
            raise ContractError(f'Missing or invalid dates in {column}')


def read_source(path: Path, spec: dict) -> pd.DataFrame:
    if path.suffix == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for line, row in enumerate(csv.reader(stream), 1):
                if len(row) != len(spec['columns']):
                    raise ContractError(f'CSV width changed at record {line}')
        frame = pd.read_csv(path, keep_default_na=False, dtype=str)
    else:
        with pd.ExcelFile(path) as workbook:
            if workbook.sheet_names != [spec['sheet']]:
                raise ContractError('Workbook sheets changed')
            frame = pd.read_excel(workbook, keep_default_na=False)
    validate_frame(frame, spec)
    return frame


def profile_frame(frame: pd.DataFrame, spec: dict, retrieved_at: str) -> dict:
    result = {'rows': len(frame), 'columns': {}, 'duplicate_rows_after_first': int(frame.duplicated().sum()),
              'candidate_key': spec['candidate_key'], 'complete_through': None,
              'grain': spec['grain'], 'measure': spec['measure']}
    if spec['candidate_key']:
        result['duplicate_keys_after_first'] = int(frame.duplicated(spec['candidate_key']).sum())
    for col in frame:
        values = frame[col].replace('', None)
        detail = {'dtype': str(frame[col].dtype), 'nulls': int(values.isna().sum()), 'distinct': int(values.nunique())}
        if col in spec['numeric_columns']:
            numeric = pd.to_numeric(values)
            detail.update(min=numeric.min(), max=numeric.max(), zero=int(numeric.eq(0).sum()), negative=int(numeric.lt(0).sum()), fractional=int((numeric.notna() & numeric.mod(1).ne(0)).sum()))
        elif col in spec['date_columns']:
            dates = pd.to_datetime(values)
            detail.update(min=str(dates.min().date()), max=str(dates.max().date()), labels_after_retrieval=int((dates > pd.Timestamp(retrieved_at).tz_localize(None)).sum()))
        else:
            detail['values'] = sorted(values.dropna().astype(str).unique().tolist())
        result['columns'][col] = detail
    return result


def lease_reconciliation(units: pd.DataFrame, values: pd.DataFrame) -> dict:
    key = ['Date', 'Property Type', 'Municipality', 'District', 'Property Layout']
    # Null dimensions are genuine source groups, never silently discarded.
    left = units.groupby(key, dropna=False, as_index=False)['Leased Units'].sum()
    right = values.groupby(key, dropna=False, as_index=False)['Sum of active_value_aed'].sum()
    joined = left.merge(right, on=key, how='outer', validate='one_to_one', indicator=True)
    return {'units_rows': len(units), 'value_rows': len(values), 'units_shared_keys': len(left), 'value_shared_keys': len(right),
            'join_counts': {str(k): int(v) for k,v in joined['_merge'].value_counts().items()},
            'units_null_key_rows': int(units[key].replace('', None).isna().any(axis=1).sum()),
            'values_null_key_rows': int(values[key].replace('', None).isna().any(axis=1).sum()),
            'derived_annual_rent_supported': False}


def profile_snapshot(snapshot: Path) -> dict:
    contract = json.loads(CONTRACT.read_text())
    entries = [json.loads(line) for line in (snapshot / 'native-export-manifest.jsonl').read_text().splitlines() if line]
    manifest = {entry['file']: entry for entry in entries}
    expected = {'native-exports/' + name for name in contract['sources']}
    if len(manifest) != len(entries) or set(manifest) != expected:
        raise ContractError('Manifest must contain every contracted native source exactly once')
    frames, reports = {}, {}
    for name, spec in contract['sources'].items():
        relative = 'native-exports/' + name
        path = snapshot / relative
        entry = manifest[relative]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry['sha256'] or path.stat().st_size != entry['bytes']:
            raise ContractError(f'Checksum/size mismatch: {name}')
        frame = read_source(path, spec)
        frames[name] = frame
        reports[name] = dict(profile_frame(frame, spec, entry['retrieved_at_utc']), sha256=digest, retrieved_at_utc=entry['retrieved_at_utc'], parameters=entry['parameters'])
    units = frames['Residential Leases/lease_residential.xlsx']
    values = frames['Residential Leases/lease_price_by_period.xlsx']
    geography = pd.concat([f[['Municipality', 'District']] for f in frames.values() if {'Municipality','District'} <= set(f.columns)]).drop_duplicates()
    ambiguous = geography.groupby('District')['Municipality'].agg(lambda x: sorted(set(x))).to_dict()
    ambiguous = {k:v for k,v in ambiguous.items() if len(v)>1}
    sales = frames['Transactions/recent_sales_2019-2026.csv']
    areas = pd.to_numeric(sales['Property Sold Area (SQM)'])
    finance = {}
    for name, frame in frames.items():
        if 'Financed Sales' in frame:
            delta = frame['Financed Sales'] + frame['Cash Sales'] - frame['Total Sales']
            finance[name] = {'nonzero_delta_rows': int(delta.abs().gt(0.01).sum()), 'max_absolute_delta': float(delta.abs().max()), 'unit_confirmed': False}
    return {'contract_version': contract['version'], 'snapshot': snapshot.name, 'sources': reports,
            'lease_join': lease_reconciliation(units, values), 'ambiguous_districts': ambiguous,
            'transaction_area_flags': {'nonpositive': int(areas.le(0).sum()), 'at_or_below_one_sqm': int(areas.le(1).sum()), 'policy': 'preserve raw values; do not derive rates from areas <= 1 sqm pending review'},
            'financing_arithmetic': finance, 'database_modified': False}
