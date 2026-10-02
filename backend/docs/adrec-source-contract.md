# Data setup and source contract

Bayan reads a private ADREC export snapshot from PostgreSQL. The repository contains the schema and import tools, but no source data or database dump. The application queries four views in the `bayan` schema: `transactions`, `rental_observations`, `price_indices`, and `dataset_coverage`. Source rows and provenance remain in the private `adrec_intake` schema.

## Prepare a snapshot

Place one snapshot in `ADREC_DATA/incoming/<snapshot-id>/`:

```text
ADREC_DATA/incoming/<snapshot-id>/
├── native-export-manifest.jsonl
└── native-exports/
    ├── Transactions/...
    ├── Residential Leases/...
    └── Price Indices/...
```

The [source contract](../app/resources/adrec_source_contract.json) lists the 31 expected filenames, sheets, columns, and accepted source categories. Keep the exports unchanged. Each JSONL manifest entry needs `file` (relative to the snapshot directory), `sha256`, `bytes`, `retrieved_at_utc`, and `parameters` (the export filters). Use a new directory name for each snapshot. Record the actual export time and filters; they cannot be inferred from a filename.

The current query surface supports transaction detail, rental observations, and price indices. Other exports are stored for provenance and reconciliation, but are not exposed as query facts. Municipality is unavailable on Recent Sales rows and remains null. District, community, project, Share, asset class, sale type, and layout keep their source meanings. A source period label does not establish a complete reporting period.

## Check the files

From the repository root, after installing `backend/requirements.txt` in `backend/.venv`, set the snapshot and database names for your own setup:

```sh
export BAYAN_SNAPSHOT_ID=2026-09-24
export BAYAN_STAGING_DB=bayan_staging_local
export BAYAN_TARGET_DB=postgres
umask 077
backend/.venv/bin/python backend/scripts/profile_snapshot.py \
  --snapshot "ADREC_DATA/incoming/$BAYAN_SNAPSHOT_ID" \
  --output /tmp/bayan-profile.json
```

The profile verifies file checksums, workbook sheets, CSV width, columns, numeric and date values, and known categories. A format failure stops import so a changed export is mapped deliberately. The JSON report records column nulls and ranges, source coverage, duplicate candidate keys, lease join coverage, geography ambiguity, small sold areas, and financing arithmetic. Its `review_items` section summarizes findings for manual review; these findings **do not stop import or change app answers**.

Review the report before loading:

- `unmatched_lease_keys`: compare `lease_join.join_counts` at Date, Property Type, Municipality, District, and Property Layout. Lease units and values have different detail levels, so keep unmatched groups visible.
- `ambiguous_districts`: inspect `ambiguous_districts`. Do not assign a municipality to a sales row by district name alone.
- `small_sold_areas`: inspect `transaction_area_flags`. Raw rows remain; Bayan leaves its calculated price per sqm null when sold area is at most 1 sqm.
- `duplicate_candidate_keys`: inspect the named source's key and rows. Repeated Recent Sales rows are retained because they have no proven unique transaction key.
- `financing_arithmetic`: inspect `financing_arithmetic` and source units before interpreting totals. Financing is not part of the public query views.

Rental comparisons and indicative gross yield need a separate analyst check when the source or business definition changes. For a multi-segment annual rent, match the comparison export to positive leased units at the same period, municipality, district, property type, and layout; weight annual rent by those units. Indicative gross segment yield uses annual rent and average sale price from the **same comparison row**, then weights matched segment ratios by leased units. Report matched segment/unit coverage. A mismatch with another published figure is a review finding, not a reason to stop the database or show an internal warning in Bayan. Net and individual-property yield are unsupported.

## Import into a new database

Use a separate PostgreSQL database named `bayan_staging_<name>` and set `BAYAN_STAGING_URL` privately to its owner connection URL. With the local Docker database from the README, create it with:

```sh
docker compose exec -e BAYAN_STAGING_DB="$BAYAN_STAGING_DB" postgres \
  sh -c 'createdb -U "$POSTGRES_USER" "$BAYAN_STAGING_DB"'
```

The import scripts require the exact expected database name and do not read the application connection URL.

```sh
backend/.venv/bin/python backend/scripts/import_snapshot.py \
  --snapshot "ADREC_DATA/incoming/$BAYAN_SNAPSHOT_ID" \
  --staging-url-env BAYAN_STAGING_URL \
  --expected-database "$BAYAN_STAGING_DB"

backend/.venv/bin/python backend/scripts/prepare_query_schema.py \
  --staging-url-env BAYAN_STAGING_URL \
  --expected-database "$BAYAN_STAGING_DB" \
  --snapshot-id "$BAYAN_SNAPSHOT_ID"
```

The importer keeps every source row with its file, checksum, and row number. Repeating the same import is safe. A different set of bytes requires a new snapshot ID. Review the staged row counts and `bayan` views before promoting them.

For a **new, empty** application database, move the two prepared schemas from staging with PostgreSQL tools. Set `BAYAN_TARGET_URL` privately to the target owner URL and verify both URLs point to the intended databases before running these commands:

```sh
pg_dump --dbname="$BAYAN_STAGING_URL" --format=custom \
  --schema=adrec_intake --schema=bayan --file=/tmp/bayan-snapshot.dump
pg_restore --dbname="$BAYAN_TARGET_URL" --no-owner --no-acl \
  --single-transaction --exit-on-error /tmp/bayan-snapshot.dump
```

Keep the dump private. For a populated database, back it up, test restoration separately, reconcile the staged snapshot, and use a reviewed promotion/rollback procedure. Do not restore over the deployed database as a first-time setup step.

Configure the target's separate API runtime and read-only query roles using the private values in `backend/.env`. These commands use `DATABASE_URL` for the owner connection; set it to the verified target URL in the command environment:

```sh
cd backend
DATABASE_URL="$BAYAN_TARGET_URL" .venv/bin/python scripts/init_runtime_store.py --database "$BAYAN_TARGET_DB"
DATABASE_URL="$BAYAN_TARGET_URL" .venv/bin/python scripts/configure_query_role.py --expected-database "$BAYAN_TARGET_DB"
DATABASE_URL="$BAYAN_TARGET_URL" .venv/bin/python scripts/configure_runtime_role.py --expected-database "$BAYAN_TARGET_DB"
```

The API uses the restricted runtime role for metadata and shared limits; generated SQL uses the separate read-only role. Keep the owner URL out of the running API and frontend. Start the app, then check `/ready` for the snapshot ID and `/api/v1/schema` for the four query views.

## Inspect stored flags

`adrec_intake.observations.quality_flags` stores row-level import flags. They are for database review, not application warnings. For example, in a private SQL session:

```sql
SELECT source_file, flag, count(*) AS rows
FROM adrec_intake.observations AS o
CROSS JOIN LATERAL jsonb_array_elements_text(o.quality_flags) AS flags(flag)
GROUP BY source_file, flag
ORDER BY source_file, flag;
```

For source-level questions, inspect the profile JSON and `adrec_intake.sources`. For application-visible data, query `bayan.dataset_coverage` and the three fact views. Monthly, quarterly, and yearly aggregates overlap; never sum them together as independent transactions.
