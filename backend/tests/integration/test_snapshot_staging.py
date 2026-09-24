"""Run only against an explicitly provided, already-imported disposable target."""
import csv
import os
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture(scope='module')
def staging():
    url = os.environ.get('BAYAN_DISPOSABLE_STAGING_URL')
    snapshot = os.environ.get('BAYAN_TEST_SNAPSHOT')
    if not url or not snapshot:
        pytest.skip('Explicit disposable staging URL and snapshot required')
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text('select current_database()')).scalar_one().startswith('bayan_staging_')
        yield connection, Path(snapshot)
    engine.dispose()


def test_every_source_row_accounted_for(staging):
    connection, snapshot = staging
    rows = connection.execute(text('SELECT s.source_file, s.source_rows, count(o.source_row) FROM adrec_intake.sources s LEFT JOIN adrec_intake.observations o USING(snapshot_id,source_file) WHERE s.snapshot_id=:id GROUP BY s.source_file,s.source_rows'), {'id':snapshot.name}).all()
    assert len(rows) == 31
    assert all(expected == actual for _,expected,actual in rows)


def test_sales_decimal_totals_and_duplicates_survive(staging):
    connection, snapshot = staging
    with (snapshot/'native-exports/Transactions/recent_sales_2019-2026.csv').open(encoding='utf-8-sig') as stream:
        records = list(csv.DictReader(stream))
    actual = connection.execute(text('SELECT count(*),sum(price_aed),sum(sold_share),count(municipality) FROM adrec_intake.transactions WHERE snapshot_id=:id'), {'id':snapshot.name}).one()
    assert actual == (len(records), sum(Decimal(r['Property Sale Price (AED)']) for r in records), sum(Decimal(r['Property Sold Share']) for r in records), 0)


def test_indices_keep_series_unique_and_rent_types_distinct(staging):
    connection, snapshot = staging
    duplicates = connection.execute(text('SELECT count(*) FROM (SELECT source_file,period_end,municipality,source_area_group,property_group,application_type FROM adrec_intake.price_indices WHERE snapshot_id=:id GROUP BY 1,2,3,4,5,6 HAVING count(*)>1) d'), {'id':snapshot.name}).scalar_one()
    assert duplicates == 0
    assert connection.execute(text("SELECT count(distinct application_type) FROM adrec_intake.price_indices WHERE snapshot_id=:id AND index_type='rent'"), {'id':snapshot.name}).scalar_one() == 2


def test_low_area_derived_rates_suppressed_without_row_loss(staging):
    connection, snapshot = staging
    assert connection.execute(text('SELECT count(*) FROM adrec_intake.transactions WHERE snapshot_id=:id AND sold_area_sqm<=1 AND calculated_rate_aed_sqm IS NOT NULL'), {'id':snapshot.name}).scalar_one() == 0
    assert connection.execute(text("SELECT count(distinct layout) FROM adrec_intake.rental_observations WHERE snapshot_id=:id AND layout IN ('5+ beds','6+ beds')"), {'id':snapshot.name}).scalar_one() == 2


def test_late_import_failure_rolls_back_snapshot_and_rows(staging, tmp_path, monkeypatch):
    import hashlib
    import json
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.genlib import snapshot_import as importer
    from sqlalchemy.exc import DBAPIError

    connection, original = staging
    snapshot = tmp_path / 'rollback-fixture'
    name = 'Transactions/recent_sales_2019-2026.csv'
    path = snapshot / 'native-exports' / name
    path.parent.mkdir(parents=True)
    with (original / 'native-exports' / name).open(encoding='utf-8-sig') as stream:
        reader = csv.reader(stream)
        sample = [next(reader), next(reader)]
    with path.open('w', newline='') as stream:
        csv.writer(stream).writerows(sample)
    spec = json.loads(importer.CONTRACT.read_text())['sources'][name]
    contract = tmp_path / 'contract.json'
    contract.write_text(json.dumps({'sources': {name: spec}}))
    broken_views = tmp_path / 'views.sql'
    broken_views.write_text('SELECT 1 / 0;')
    monkeypatch.setattr(importer, 'CONTRACT', contract)
    monkeypatch.setattr(importer, 'VIEWS', broken_views)
    monkeypatch.setattr(importer, 'profile_snapshot', lambda _: {'contract_version': 1, 'sources': {name: {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'rows': 1, 'retrieved_at_utc': '2026-09-24T00:00:00Z', 'grain': 'source_observation', 'measure': 'source_label'}}})
    database = connection.execute(text('select current_database()')).scalar_one()
    with pytest.raises(DBAPIError):
        importer.import_snapshot(connection.engine, snapshot, database)
    assert connection.execute(text("SELECT count(*) FROM adrec_intake.snapshots WHERE snapshot_id='rollback-fixture'")).scalar_one() == 0
    assert connection.execute(text("SELECT count(*) FROM adrec_intake.observations WHERE snapshot_id='rollback-fixture'")).scalar_one() == 0
