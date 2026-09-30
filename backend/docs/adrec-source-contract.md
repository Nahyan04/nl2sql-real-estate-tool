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

Preserve district, community, project, asset class, layout, sale application type, sale sequence and fractional Share exactly. Bayan interprets Share as the fraction of ownership interest transferred: 1 means a whole interest, and a positive fraction below 1 means a partial interest. It is neither a row count nor a multiplier for recorded price or area. Municipality is absent from Recent Sales and must remain unresolved; cross-source district labels do not establish a parent relationship. Never pair EN/AR lookup lists by position. Keep 5+ beds and 6+ beds separate. All asset classes and industrial series are retained for profiling; publication scope remains a later explicit decision.

## Metrics and coverage

Keep each source's fact/period date separate from retrieval time. Dates past retrieval are period labels, not future facts. `complete_through` remains null for every dataset because a past month-end alone does not prove reporting completeness. Recent Sales is observed detail through its own maximum date, not a complete market census.

Lease units and values join at Date, Property Type, Municipality, District and Property Layout, with null groups retained and an outer join. The ADREC H1 2026 report defines active leases as period-end stock and residential lease value as annual rent value accrued over the stated period. The native Q1+Q2 2026 `Sum of active_value_aed` totals AED 9,324,978,842 at Emirate scope, consistent with the report's rounded AED 9.3bn H1 value. Treat each export quarter as source lease value for that quarter; sum non-overlapping quarters for a half-year value, never annualize one quarter. Native Q2 `Leased Units` totals 228,456 versus the report's 233,000 active leases, so label it source quarter-end leased units rather than the report's stock count or new contracts.

For an annual-rent estimate spanning several segments, use the comparison export's `Annual Rent` at one quarter and join the lease-unit export at the exact shared key: period end, municipality, district, property type and layout. Aggregate lease-unit rows to that key before joining, because their community/project dimensions are finer. Weight each positive annual-rent observation by its positive quarter-end leased-unit count: `SUM(annual_rent * leased_units) / SUM(leased_units)`. Do not re-average the monthly `rolling_average` values; they remain directly reportable at their original segment grain.

For an indicative gross rental-yield estimate, require both positive `Annual Rent` and positive `Average of average_sale_price_aed` on the **same comparison-export row**. The segment ratio is `100 * annual_rent / average_sale_price_aed`; a multi-segment estimate is the leased-unit-weighted mean of those matched ratios. Include the matched segment and unit counts so the smaller sale-observed population is visible. At Q2 2026, 703 of 706 comparison rent segments match positive leased-unit weights (220,547 units), giving AED 79,231 as the weighted annual-rent estimate. Only 90 segments also have positive sale price (56,870 matched units), giving an indicative gross yield of 5.74%. This is a segment-level gross estimate before costs, not a property-specific or net yield. Do not combine Recent Sales transaction prices with lease observations for this calculation.

Index keys retain municipality, Zone/District, original property group, App Type and date. Zone/District in index exports can mean investment-zone grouping rather than a named district. Keep all-rents and new-rents separate. The ADREC H1 2026 report describes a same-unit repeat lease index rebased to Q1 2020; native June 2025 to June 2026 rates match its rounded figures. The exact monthly estimator remains unpublished, so compare only within one source series.

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

Install the shared limiter tables with `python scripts/init_runtime_store.py --database <working-name>`, then run `python scripts/configure_runtime_role.py --expected-database <working-name>` with `RUNTIME_DB_PASSWORD` in private server configuration. The API process uses this restricted role for snapshot metadata and shared rate-limit writes; generated SQL uses the separate read-only role. Keep the bootstrap/migration URL out of the public API process.

The configured local working database was promoted on September 25, 2026 after backup/restore verification. Its public schema had no user tables. The only application data is now the September 24 native snapshot; old source files and generation paths are removed. Rollback backups are recovery artifacts, not a runtime data source.
