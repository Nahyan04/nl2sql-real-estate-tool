# Bayan — Natural-Language Analytics for Real Estate

Bayan answers English and Arabic questions about Abu Dhabi real estate with validated PostgreSQL, source-backed results and charts. It is an analyst query and evidence layer complementing ADREC's dashboards and existing AI tools, not an official ADREC integration.

The application uses the real ADREC native exports received on September 24, 2026. There is no synthetic generator, legacy seed path or legacy runtime mode.

## Data and supported scope

The active snapshot contains 240,490 source observations across 31 native files, including 122,936 Recent Sales observations. The query surface exposes sales, source rental observations, geographically distinct price indices and per-source coverage. Raw imports are private to the importer.

- Sales preserve district, community, project, asset class, source sale type, layout and fractional Share. Municipality is unknown when absent from the source.
- Repeated-looking sales remain separate observations because no stable transaction ID is provided.
- Rental values retain source labels. Annualization, yield and weighted rent comparisons remain unsupported until definitions are confirmed.
- Indices preserve geography, property grouping and all-rents/new-rents distinctions.
- There are no fabricated developer, broker or lender records. Financing aggregates remain in source storage but are not exposed while their units are unresolved.
- Download date is not data completeness. Use `dataset_coverage` to inspect each source's actual dates; a future period-end label does not prove a complete period.

See the [source contract and import guide](backend/docs/adrec-source-contract.md).

## Architecture

Python/FastAPI and a thin LangGraph pipeline retrieve the source schema, generate SQL, validate permitted relations/functions, execute a bounded read-only transaction, and synthesize the answer. Next.js/React renders the SQL, table and appropriate chart. Anthropic and self-hosted Ollama are configured server-side; provider selection never silently falls back.

Generated queries can access only `bayan.transactions`, `bayan.rental_observations`, `bayan.price_indices` and `bayan.dataset_coverage`. These views select one active snapshot. The read-only database role cannot select raw intake tables. Unsupported model responses terminate without executing SQL or retrying generation.

## Local setup

1. Configure `backend/.env` from `backend/.env.example` and the frontend environment from `frontend/.env.local.example`. Keep credentials server-side.
2. Start PostgreSQL with `docker compose up -d postgres`.
3. Import and verify the native snapshot in a separate staging database using the guide. Back up the intended working database, test restoration, then promote the verified `adrec_intake` and `bayan` schemas. There is no generated-data seed command.
4. From `backend/`, run `python scripts/configure_query_role.py --expected-database <database-name>` after promotion. It uses the existing configured read-only password and refuses unexpected public tables.
5. Start the API with `uvicorn app.main:app --reload` and the frontend with `npm run dev` from `frontend/`.

Startup requires an installed source query schema and validated active snapshot. `/health` reports process/database connectivity; `/ready` checks the source query schema and returns the active snapshot. `/api/v1/schema` exposes only the four query views.

## Verification

Run backend unit tests from `backend/` with `python -m pytest tests/unit -q`. The focused API smoke test uses a mocked model and the configured populated fresh database. Staging integration tests require explicit `BAYAN_DISPOSABLE_STAGING_URL` and, for source reconciliation, `BAYAN_TEST_SNAPSHOT`.

The reference questions were replaced with source-supported sales queries. Previous evaluation scores no longer describe this build. Live model evaluation remains opt-in and requires a separate agreed budget.

For frontend changes, run `npm run lint` and `npx tsc --noEmit` from `frontend/`.

## License

This project is provided as-is for demonstration purposes.
