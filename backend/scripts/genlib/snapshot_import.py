"""Transactional native-source staging import."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from .source_contract import CONTRACT, ContractError, profile_snapshot, read_source

DDL = Path(__file__).resolve().parents[2] / 'db/adrec_staging.sql'
VIEWS = Path(__file__).resolve().parents[2] / 'db/adrec_views.sql'


def source_records(frame, spec):
    """Keep source labels, missing values and precision; no inferred geography."""
    metrics = set(spec['numeric_columns'])
    for ordinal, row in enumerate(frame.to_dict('records'), 1):
        dimensions, measures = {}, {}
        flags = []
        for column, value in row.items():
            if pd.isna(value) or value == '':
                value = None
            elif isinstance(value, (pd.Timestamp,)) or hasattr(value, 'isoformat'):
                value = value.isoformat()
            else:
                value = str(value)
            (measures if column in metrics else dimensions)[column] = value
        if 'Property Sold Area (SQM)' in measures:
            area = measures['Property Sold Area (SQM)']
            if area is None:
                flags.append('missing_sold_area')
            elif float(area) <= 1:
                flags.append('sold_area_at_or_below_one_sqm')
            flags.append('municipality_not_provided')
        yield {'source_row': ordinal, 'dimensions': json.dumps(dimensions, ensure_ascii=False),
               'metrics': json.dumps(measures, ensure_ascii=False), 'quality_flags': json.dumps(flags)}


def import_snapshot(engine, snapshot: Path, expected_database: str) -> dict:
    # An explicit disposable/staging target is mandatory, even if env config points elsewhere.
    if not expected_database.startswith('bayan_staging_'):
        raise ContractError('Target database must have the bayan_staging_ prefix')
    report = profile_snapshot(snapshot)
    specs = json.loads(CONTRACT.read_text())['sources']
    snapshot_id = snapshot.name
    contract_hash = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    with engine.begin() as connection:
        actual = connection.execute(text('SELECT current_database()')).scalar_one()
        if actual != expected_database:
            raise ContractError('Connected database does not match explicit target')
        connection.execute(text("SELECT pg_advisory_xact_lock(836492170)"))
        connection.execute(text(DDL.read_text()))
        existing = connection.execute(text('SELECT contract_sha256, status FROM adrec_intake.snapshots WHERE snapshot_id=:id'), {'id': snapshot_id}).first()
        if existing:
            old = dict(connection.execute(text('SELECT source_file, sha256 FROM adrec_intake.sources WHERE snapshot_id=:id'), {'id':snapshot_id}).all())
            expected = {name: source['sha256'] for name, source in report['sources'].items()}
            if old != expected or existing.contract_sha256 != contract_hash or existing.status != 'validated':
                raise ContractError('Existing snapshot differs or is not validated; use a new snapshot identity')
            counts = dict(connection.execute(text('SELECT source_file, count(*) FROM adrec_intake.observations WHERE snapshot_id=:id GROUP BY source_file'), {'id':snapshot_id}).all())
            if counts != {name: source['rows'] for name, source in report['sources'].items()}:
                raise ContractError('Existing snapshot row accounting failed')
            return {'snapshot': snapshot_id, 'status': 'already_imported', 'rows': sum(counts.values())}
        connection.execute(text("INSERT INTO adrec_intake.snapshots(snapshot_id,contract_version,contract_sha256,status) VALUES (:id,:version,:hash,'staging')"), {'id': snapshot_id, 'version':report['contract_version'], 'hash':contract_hash})
        total = 0
        for name, spec in specs.items():
            source = report['sources'][name]
            path = snapshot / 'native-exports' / name
            # Validate the same bytes used for loading, including a concurrent-file-change check.
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            frame = read_source(path, spec)
            after = hashlib.sha256(path.read_bytes()).hexdigest()
            if before != source['sha256'] or after != before:
                raise ContractError('Source changed during import')
            connection.execute(text('INSERT INTO adrec_intake.sources(snapshot_id,source_file,sha256,retrieved_at,source_rows,grain,measure) VALUES (:id,:file,:hash,:retrieved,:rows,:grain,:measure)'), {'id':snapshot_id,'file':name,'hash':before,'retrieved':source['retrieved_at_utc'],'rows':len(frame),'grain':source['grain'],'measure':source['measure']})
            statement = text('INSERT INTO adrec_intake.observations(snapshot_id,source_file,source_row,dimensions,metrics,quality_flags) VALUES (:snapshot_id,:source_file,:source_row,CAST(:dimensions AS jsonb),CAST(:metrics AS jsonb),CAST(:quality_flags AS jsonb))')
            batch = []
            for record in source_records(frame, spec):
                batch.append(dict(record, snapshot_id=snapshot_id, source_file=name))
                if len(batch) == 1000:
                    connection.execute(statement, batch)
                    batch = []
            if batch:
                connection.execute(statement, batch)
            count = connection.execute(text('SELECT count(*) FROM adrec_intake.observations WHERE snapshot_id=:id AND source_file=:file'), {'id':snapshot_id,'file':name}).scalar_one()
            if count != source['rows']:
                raise ContractError('Source row accounting failed')
            total += count
        connection.execute(text(VIEWS.read_text()))
        connection.execute(text("UPDATE adrec_intake.snapshots SET status='validated' WHERE snapshot_id=:id"), {'id':snapshot_id})
    return {'snapshot':snapshot_id, 'status':'imported', 'rows':total}
