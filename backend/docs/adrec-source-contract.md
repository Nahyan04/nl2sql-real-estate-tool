# ADREC native source contract

The fresh-data path takes an explicit incoming snapshot and never falls back to older exports or synthetic records. Native workbooks/CSV are primary; overlapping JSON responses are evidence only. The existing application remains on its legacy schema until a separately verified staging migration and promotion. Do not point the old positional loader at these new files.

From the repository root:

```sh
backend/.venv/bin/python backend/scripts/profile_snapshot.py \
  --snapshot ADREC_DATA/incoming/2026-09-24 \
  --output .agent-notes/data-profile/profile.json
```

This read-only command validates all 31 manifest entries, hashes, sizes, sheets, exact headers/order, CSV widths, numeric/date parsing and categorical domains against `backend/app/resources/adrec_source_contract.json`. Unexpected categories fail for review instead of becoming Other. The report contains nulls, categories, numeric ranges, fractional values, duplicate candidates, source coverage, lease outer-join accounting, ambiguous districts and financing arithmetic. Incoming files must never be rewritten. Snapshot-specific reports remain local, not committed.

## Grain and identity

Every source has an independent contract, measure and grain. Monthly, quarterly and yearly exports overlap and must never be added together. Count/AED is selected from the manifest-backed source filename, not inferred from the ambiguous value column. Financing unit definitions remain unresolved even when cash + financed equals total.

Workbook candidate keys comprise all non-measure columns, including period labels and geography. A candidate key is a profiling assertion, not permission to discard duplicates. Recent Sales has no proven natural key: preserve every row, including identical-looking observations. Its ingestion identity is snapshot + source file + one-based data-row ordinal, backed by the source checksum. This identity does not permit incremental appends across snapshots.

Preserve district, community, project, asset class, layout, sale application type, sale sequence and fractional Share exactly. Share is not a row count. Municipality is absent from Recent Sales and must remain unresolved; cross-source district labels do not establish a parent relationship. Never pair EN/AR lookup lists by position. Keep 5+ beds and 6+ beds separate. All asset classes and industrial series are retained for profiling; publication scope remains a later explicit decision.

## Metrics and coverage

Keep each source's fact/period date separate from retrieval time. Dates past retrieval are period labels, not future facts. `complete_through` remains null for every dataset because a past month-end alone does not prove reporting completeness. Recent Sales is observed detail through its own maximum date, not a complete market census.

Lease units and values join at Date, Property Type, Municipality, District and Property Layout, with null groups retained and an outer join. The native Leased Units label does not establish occupied stock or contract flow. Preserve `Sum of active_value_aed`; do not rename it annual rent or apply a multiplier. The rolling annual-rent export lacks a confirmed window/weighting definition; the price comparison lacks proven comparable populations/units. Yield, annualization and weighted cross-source comparisons remain unsupported pending evidence.

Index keys retain municipality, Zone/District, original property group, App Type and date. Zone/District in index exports can mean investment-zone grouping rather than a named district. Keep all-rents and new-rents separate. Index values starting at 100 in January 2020 do not prove an official base methodology.

Preserve raw area/rate fields. Null, nonpositive and very small sold areas require quality flags; suppress newly calculated per-area rates for areas <= 1 sqm pending investigation. This threshold is a conservative quality policy, not a claim that every such record is invalid.

## Schema and seed transition

`backend/db/adrec_staging.sql` defines a separate intake schema, source provenance and lossless observation records. Dimensions and metrics retain their native names; no curated geography, developer, broker or loan rows are seeded. It intentionally grants no access to the application role. It is applied only to an explicitly named staging database; the working database is unchanged.

The intake schema is a preservation layer. `adrec_views.sql` supplies typed transaction, index, rental-observation and aggregate views without losing raw source labels. `import_snapshot.py` loads every source in one transaction, checks row accounting, and rejects a reused snapshot identity with changed hashes/contracts. Repeated identical imports are no-ops after count verification. Next: establish application-facing views and metadata, back up and test restoration of the intended working target, update retrieval/SQL allowlists, then promote with rollback. A reused snapshot ID must reject changed hashes. Never treat `CREATE TABLE IF NOT EXISTS` as a schema migration system.

Legacy `schema.sql`, `reference_seed.sql`, `real_loader.py` and the synthetic generator remain isolated compatibility code during migration. The two destructive setup commands now require `--allow-legacy-reset`; neither is appropriate for fresh-data refresh. Removing them or changing the application's tables before consumer migration would break the existing application.

## Import into an isolated staging database

Create a separate PostgreSQL database whose name starts with `bayan_staging_`. Put its connection URL in a dedicated environment variable, then run:

```sh
backend/.venv/bin/python backend/scripts/import_snapshot.py \
  --snapshot ADREC_DATA/incoming/2026-09-24 \
  --staging-url-env BAYAN_STAGING_URL \
  --expected-database bayan_staging_review
```

The importer verifies the actual database name and refuses mismatches before DDL. It never reads the application's database configuration. The staging target must be private and dedicated; no application read-only grants are created. A transaction-scoped lock serializes imports. Sources are rechecked during loading, numeric CSV strings preserve decimal precision, and all source rows survive. Schema version 1 requires a fresh staging schema; future schema changes need an explicit migration.

Staging snapshot status `validated` means source shape, checksums and row accounting passed; it is not an assertion that unresolved business definitions or application acceptance have passed. Full native files are the only seed input; reference names are taken directly from source observations. No fabricated dimension relationships are seeded.
