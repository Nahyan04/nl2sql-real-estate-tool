# Bayan — Natural-Language Analytics for Real Estate

Bayan answers English and Arabic questions about Abu Dhabi real estate with validated PostgreSQL, source-backed results and charts. It is an analyst query and evidence layer complementing ADREC's dashboards and existing AI tools, not an official ADREC integration.

The application uses the real ADREC native exports received on September 24, 2026. There is no synthetic generator, legacy seed path or legacy runtime mode.

## Data and supported scope

The active snapshot contains 240,490 source observations across 31 native files, including 122,936 Recent Sales observations. The query surface exposes sales, source rental observations, geographically distinct price indices and per-source coverage. Raw imports are private to the importer.

- Sales preserve district, community, project, asset class, source sale type, layout and fractional Share. Bayan treats Share as the ownership fraction transferred; recorded sale price and area are not rescaled. Municipality is unknown when absent from the source.
- Repeated-looking sales remain separate observations because no stable transaction ID is provided.
- Quarterly lease values can be summed across distinct periods; leased-unit counts describe a quarter end. For broader annual-rent estimates, Bayan weights same-quarter, same-segment comparison rents by exported leased-unit counts. Indicative gross yield compares annual rent and sale price from the same segment row, then weights matched segment ratios by leased units. For an individual or net yield question, Bayan can show this gross segment estimate as a proxy while stating that property costs and individual prices are needed for the requested net figure.
- Indices preserve geography, property grouping and all-rents/new-rents distinctions.
- There are no fabricated developer, broker or lender records. Financing aggregates remain in source storage but are not exposed while their units are unresolved.
- Download date is not data completeness. Use `dataset_coverage` to inspect each source's actual dates; a future period-end label does not prove a complete period.

See the [source contract and import guide](backend/docs/adrec-source-contract.md).

## Architecture

Python/FastAPI and a thin LangGraph pipeline retrieve the source schema, generate SQL, validate permitted relations/functions, execute a bounded read-only transaction, and synthesize the answer. Narrow verified query plans cover explicit Al Reem Island apartment rent/yield, quarterly residential lease value and leased units, Abu Dhabi City residential rent-index levels and comparisons, Al Bateen source-district value, plain annual sales counts and values, and source sale-type or district rankings. These plans use the same SQL validation and execution path, and the UI identifies them. They apply only when their stated filters match; other questions use the selected model for SQL and prose. The Al Bateen plan matches the source Arabic district name البطين when a question explicitly names the district, and does not assign a municipality to sales rows. Next.js/React renders the SQL, table and appropriate chart. Anthropic and self-hosted Ollama are configured server-side; provider selection never silently falls back.

Generated queries can access only `bayan.transactions`, `bayan.rental_observations`, `bayan.price_indices` and `bayan.dataset_coverage`. These views select one active snapshot. The read-only database role cannot select raw intake tables. Unsupported model responses terminate without executing SQL or retrying generation.

## Local setup

1. Configure `backend/.env` from `backend/.env.example` and the frontend environment from `frontend/.env.local.example`. Keep credentials server-side.
2. Start PostgreSQL with `docker compose up -d postgres`.
3. Import and verify the native snapshot in a separate staging database using the guide. Back up the intended working database, test restoration, then promote the verified `adrec_intake` and `bayan` schemas. There is no generated-data seed command.
4. From `backend/`, run `python scripts/configure_query_role.py --expected-database <database-name>` after promotion. It uses the existing configured read-only password and refuses unexpected public tables.
5. From `backend/`, run `python -m scripts.init_runtime_store --database <database-name>` to install the shared request guard tables. This command checks the database name and does not modify source observations.
6. Start the API with `uvicorn app.main:app --reload --no-proxy-headers` and the frontend with `npm run dev` from `frontend/`.

Startup requires an installed source query schema and validated active snapshot. `/health` reports process/database connectivity; `/ready` checks the source query schema and shared request guard tables, then returns the active snapshot. `/api/v1/schema` exposes only the four query views.

For a reasoning-capable Ollama model, `OLLAMA_REASONING=false` in the server environment disables thinking output when it makes simple queries exceed the request limit. Leave it unset for a model without that option. The selected Ollama model and endpoint remain server configuration; provider selection never changes the model silently.

Query errors use a stable `error` code, a safe user-facing `detail`, and a `request_id` also returned in `X-Request-ID`. Keep the request ID when investigating server logs; raw provider and database exception text is not returned to clients. Malformed requests return `INVALID_REQUEST` with HTTP 422.

Unsupported topics and ambiguous places or relative dates stop before SQL execution; the latter return `CLARIFICATION` so the user can name an exact period or source place. Explicit Al Bateen district questions can be answered across source sales rows, while a municipality-specific Al Bateen sales request remains ambiguous because the sales export has no municipality field. If a model asks for a period already present in the question, one bounded generation retry points out the stated year; a remaining ambiguity still returns `CLARIFICATION`. Explicit years and quarters remain queryable even when source completeness is unconfirmed. Successful responses include `outcome` (`answer` or `no_data`), resolved `language` (`en` or `ar`) and `answer_limited` when the synthesis saw only part of the returned rows or the query result was truncated.

For the ready residential apartment rate question, a scope check rejects SQL that omits the explicit ready, residential, apartment or sold-area filter and asks the model to repair it within the configured attempt limit. Answers report the returned average without inventing a source-row count from SQL's result limit.

`POST /api/v1/query` accepts `language: "auto" | "en" | "ar"` alongside the question and provider. Auto chooses Arabic when the question contains Arabic script; the explicit options override that choice for both the answer and interface. Model prose that misses the selected language is retried once, then returned as `LANGUAGE_MISMATCH` rather than shown in the wrong language. The frontend's New question control clears the current request and result while keeping session question history available.

The frontend shows a concise analysis status with elapsed browser wait time while a request is running. Results include the executed SQL's date conditions, actual used tables, metric units inferred from result aliases, the snapshot ID and source coverage only for files explicitly named by the query (or the sole sales source). A missing date condition is shown explicitly rather than treated as an inferred reporting window.

If the selected model fails during SQL generation or answer synthesis, the API returns `PROVIDER_UNAVAILABLE` instead of an empty answer. The question remains in the input for retry.

The query route uses PostgreSQL for atomic limits across API workers. Default allowances are 30 requests/minute and 300/day per browser session, plus 120/minute and 1,200/day per client IP; at most eight requests run concurrently across workers. These are configurable server-side. A rejected request returns HTTP 429 and `Retry-After`; an unavailable guard returns HTTP 503 and no model call. Direct API requests are subject to the IP limit. Configure `CORS_ORIGINS` for the frontend and `TRUSTED_PROXY_CIDRS` only for proxies you control; keep Uvicorn proxy-header rewriting disabled so untrusted forwarding headers cannot choose their own rate-limit identity. Use the same hostname for local frontend/API URLs so the session cookie persists. For a cross-site HTTPS frontend, set `SESSION_COOKIE_SECURE=true` and `SESSION_COOKIE_SAMESITE=none`. Anthropic credit restrictions are managed in the provider console; Bayan does not impose a separate dollar cap.

## Verification

Run backend unit tests from `backend/` with `python -m pytest tests/unit -q`. The focused API smoke test uses a mocked model and the configured populated fresh database. Staging integration tests require explicit `BAYAN_DISPOSABLE_STAGING_URL` and, for source reconciliation, `BAYAN_TEST_SNAPSHOT`.

The reference set covers sales, rental value, leased units, rent-index growth, weighted rent, indicative yield and EN/AR boundary cases. Previous evaluation scores no longer describe this build. Run `python scripts/run_eval.py --provider anthropic --workers 1 --input-rate <USD per million> --output-rate <USD per million> --json <private report path>` only with an agreed live budget and model-specific current rates. The report records model, snapshot, row grade, answer language, tokens, latency and estimated uncached token cost; manually review narrative claims and preserve failed cases.

For frontend changes, run `npm run lint` and `npx tsc --noEmit` from `frontend/`.

## License

This project is provided as-is for demonstration purposes.
