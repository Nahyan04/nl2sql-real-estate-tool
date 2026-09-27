"""Fresh-data query contract; no discovery of legacy or raw intake relations."""
from sqlalchemy import inspect, text

from app.services.schema_introspector import build_table_metadata

PRODUCT_RELATIONS = frozenset({'transactions', 'price_indices', 'rental_observations', 'dataset_coverage'})

DESCRIPTIONS = {
    'transactions': 'One exported sales observation per row; repeated-looking rows retained. Municipality unknown. District/community/project are separate source fields. Interpret sold_share as transferred ownership fraction (1 = whole interest), not transaction count; never rescale recorded price or area by it. Use sale_type ready/off-plan/court-mandated separately. Keep 5+ beds and 6+ beds distinct. Raw and quality-screened calculated area rates are separate.',
    'price_indices': 'One observation per source_file, period_end, municipality, source_area_group, property_group, application_type. Filter one series before comparing periods. Area group can be an investment-zone grouping, not a district. Keep all-rents and new-rents separate. The residential repeat-lease rent index is rebased to Q1 2020; exact monthly weighting is unpublished.',
    'rental_observations': 'Separate source observations identified by source_file. Quarterly active_value_aed is residential lease value accrued in that period; sum only non-overlapping periods. Source leased units are quarter-end counts. Monthly source_rolling_average_aed is reported only at its own segment grain. For a quarter-level broader rent estimate, weight comparison-source source_annual_rent by positive leased units joined at exact period/municipality/district/property_type/layout. Indicative gross yield is comparison-source annual rent divided by sale price at the same positive-valued segment, with leased-unit-weighted segment ratios for rollups; show matched coverage. No individual-property or net yield.',
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
