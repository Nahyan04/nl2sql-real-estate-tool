# ADREC native source contract

The fresh-data path takes an explicit incoming snapshot and never falls back to older exports or synthetic records. Native workbooks/CSV are primary; overlapping JSON responses are evidence only. The application reads only the `bayan` query views over one active native snapshot. Legacy loaders, seeds, synthetic generators and the old export copies have been removed.

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

The intake schema preserves native rows. `adrec_views.sql` provides source-preserving typed views; `bayan_query_v1.sql` exposes the three supported fact views and `dataset_coverage` for one active snapshot. The application role has SELECT only on those four query views. Unsupported finance aggregates remain in private source storage.

`import_snapshot.py` loads every source in one transaction, verifies row accounting, rejects changed hashes under an existing snapshot identity, and makes identical repeat imports no-ops. `prepare_query_schema.py` installs the versioned query schema and selects the validated snapshot. No curated geography or synthetic seed records are used.

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

## Query schema and promotion

After importing, prepare the query surface in the same staging database:

```sh
backend/.venv/bin/python backend/scripts/prepare_query_schema.py \
  --staging-url-env BAYAN_STAGING_URL \
  --expected-database bayan_staging_review \
  --snapshot-id 2026-09-24
```

Back up the explicitly identified working database and restore that backup in a separate target first. Export only `adrec_intake` and `bayan` from the verified staging database and restore them into the prepared working target in one transaction. Do not overwrite an unknown populated target. Keep the backup outside tracked files. Existing populated schemas require an explicit reviewed replacement; the importer does not drop them automatically.

From `backend/`, run `python scripts/configure_query_role.py --expected-database <working-name>` to create/update the dedicated role using `READONLY_DB_PASSWORD` from server configuration. The script refuses unexpected public tables, privileged/inherited query roles, or residual access to private source tables. Restart the API to clear engine state and verify `/ready`, `/api/v1/schema` and a source-supported query.

The configured local working database was promoted on September 25, 2026 after backup/restore verification. Its public schema had no user tables. The only application data is now the September 24 native snapshot; old source files and generation paths are removed. Rollback backups are recovery artifacts, not a runtime data source.
