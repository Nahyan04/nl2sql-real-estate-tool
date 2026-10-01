# Bayan

Bayan is a bilingual English/Arabic analyst prototype for Abu Dhabi real estate. Ask a question and inspect its answer, executed read-only SQL, source-backed rows, chart, and data coverage. It complements ADREC's dashboards and AI tools; it is not an official ADREC service.

The application uses a private snapshot of real ADREC exports. It does not download or generate that data when the repository is cloned. Sales, rental observations, and price indices are supported. Developer ownership, broker records, and loan-level analysis are not available.

## Run locally

You need Docker and a populated Bayan PostgreSQL volume or the private ADREC snapshot. The repository does not include the real source data.

1. Copy `.env.example` to `.env`, `backend/.env.example` to `backend/.env`, and `backend/.env.runtime.example` to `backend/.env.runtime`.
2. Set matching PostgreSQL bootstrap, runtime and read-only passwords in the indicated files. Keep these files private. On an existing populated volume, retain its original bootstrap credentials.
3. Configure Cloud API with `ANTHROPIC_API_KEY`, or local Self-hosted with a running Ollama model and `OLLAMA_ENABLED=true`. The Docker API reaches host Ollama at `host.docker.internal:11434`.

```sh
docker compose up -d postgres
```

On a new machine, import the private snapshot using the [source contract and import guide](backend/docs/adrec-source-contract.md). Then install the shared limiter tables and configure the query and API runtime roles. The commands below use the default `postgres` database; replace that name if your verified target differs. The repository contains no public database dump; do not run legacy seed commands against an existing database.

The import tools and local backend checks use Python 3.11:

```sh
python3.11 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd backend
.venv/bin/python scripts/init_runtime_store.py --database postgres
.venv/bin/python scripts/configure_query_role.py --expected-database postgres
.venv/bin/python scripts/configure_runtime_role.py --expected-database postgres
cd ..
```

Once the database is populated:

```sh
docker compose up --build -d
curl http://localhost:8000/ready
```

Open [http://localhost:3000](http://localhost:3000). `/ready` should report `ready` and a snapshot ID. `docker compose down` stops the app while retaining its named PostgreSQL volume.

For frontend development, keep PostgreSQL and the API running, then use `cd frontend && npm ci && npm run dev` instead of the Compose frontend service. The local API URL is in `frontend/.env.local.example`.

## Use

Choose English, Arabic, or automatic language detection, then select an example or enter a question. Results show the answer, the SQL actually executed, source rows, a chart when useful, and snapshot/coverage evidence. Source period labels do not prove complete reporting periods. The Self-hosted control is enabled only when the server can reach its configured Ollama endpoint and find the configured model. Otherwise it is visibly unavailable; there is no silent provider switch.

## Check a change

```sh
cd backend && .venv/bin/python -m pytest tests/unit -q
cd ../frontend && npm run lint && npx tsc --noEmit && npm run build
```

Database integration tests require an explicitly disposable, populated staging database. The [import guide](backend/docs/adrec-source-contract.md) documents the data contract and refresh procedure.

## Deployment preparation

For a free prototype, use the [Neon + Render + Vercel guide](docs/deploy-free.md). Vercel hosts `frontend/`; the API and validated PostgreSQL snapshot need separate hosts. Public release requires a fresh browser and provider check against the deployed build.

## License

Provided as a demonstration prototype.
