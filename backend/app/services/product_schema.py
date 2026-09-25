"""Fresh-data query contract; no discovery of legacy or raw intake relations."""
from sqlalchemy import inspect, text

from app.services.schema_introspector import build_table_metadata

PRODUCT_RELATIONS = frozenset({'transactions', 'price_indices', 'rental_observations', 'dataset_coverage'})

DESCRIPTIONS = {
    'transactions': 'One exported sales observation per row; repeated-looking rows retained. Municipality unknown. District/community/project are separate source fields. sold_share preserves the source Share value, including fractions; its fuller definition is unresolved and it is never a transaction count. Use sale_type ready/off-plan/court-mandated separately. Keep 5+ beds and 6+ beds distinct. Raw and quality-screened calculated area rates are separate.',
    'price_indices': 'One observation per source_file, period_end, municipality, source_area_group, property_group, application_type. Filter a single series before comparing periods. Area group is investment-zone grouping, not necessarily a district. All-rents and new-rents separate. Base methodology unknown.',
    'rental_observations': 'Separate source observations, identified by source_file. Quarterly units and active_value_aed are not proven occupied stock or annual rent. Monthly source_rolling_average_aed has unknown weighting/window. Comparison source annual rent has unconfirmed units/populations. Never derive yield or annualize, sum snapshots, or average averages.',
    'dataset_coverage': 'Source coverage of the active snapshot; observed_through is a fact date or period label, not proof of completeness. complete_through is unknown when null. Monthly/quarterly/yearly aggregate exports overlap; source_rows counts source cells, not market transactions.',
}
ALIASES = {
    'sales': ['transactions'], 'مبيعات': ['transactions'], 'بيع': ['transactions'],
    'district': ['transactions'], 'منطقة': ['transactions'], 'project': ['transactions'],
    'rent': ['rental_observations', 'price_indices'], 'إيجار': ['rental_observations', 'price_indices'],
    'index': ['price_indices'], 'مؤشر': ['price_indices'],
    'coverage': ['dataset_coverage'], 'snapshot': ['dataset_coverage'],
}


def introspect_product_schema(engine):
    inspector = inspect(engine)
    views = set(inspector.get_view_names(schema='bayan'))
    if not PRODUCT_RELATIONS <= views:
        raise ValueError('Fresh-data query schema is not installed')
    with engine.connect() as connection:
        version = connection.execute(text('SELECT version FROM bayan.schema_version')).scalars().all()
        active = connection.execute(text('''SELECT a.snapshot_id FROM bayan.active_snapshot a
            JOIN adrec_intake.snapshots s USING(snapshot_id) WHERE s.status='validated' ''')).scalars().all()
        populated = connection.execute(text('SELECT EXISTS(SELECT 1 FROM bayan.transactions) AND EXISTS(SELECT 1 FROM bayan.price_indices) AND EXISTS(SELECT 1 FROM bayan.rental_observations)')).scalar_one()
        if version != [1] or len(active) != 1 or not populated:
            raise ValueError('Fresh-data snapshot is not ready')
    tables = []
    for name in sorted(PRODUCT_RELATIONS):
        table = build_table_metadata(inspector, name, 'bayan')
        table['description'] = DESCRIPTIONS[name]
        tables.append(table)
    return {'schema': 'bayan', 'snapshot_id': active[0], 'tables': tables}
