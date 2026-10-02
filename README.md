# Bayan

Bayan is a bilingual English/Arabic analyst prototype for Abu Dhabi real estate. Ask a question and inspect its answer, executed read-only SQL, source-backed rows, chart, and data coverage. It complements ADREC's dashboards and AI tools; it is not an official ADREC service.

The application uses a private snapshot of real ADREC exports. It does not download or generate that data when the repository is cloned. Sales, rental observations, and price indices are supported. Developer ownership, broker records, and loan-level analysis are not available.

## Run locally

You need Docker and a private ADREC export snapshot prepared for Bayan. The repository does not include source data or a database dump. If you already have a populated Bayan PostgreSQL database, keep its existing data and credentials.

1. Copy `.env.example` to `.env`, `backend/.env.example` to `backend/.env`, and `backend/.env.runtime.example` to `backend/.env.runtime`.
2. Set the PostgreSQL owner, runtime, and read-only passwords in those files. Keep them private. An existing PostgreSQL volume must use its original owner credentials.
3. Configure Cloud API with `ANTHROPIC_API_KEY`, or Self-hosted with a running Ollama model and `OLLAMA_ENABLED=true`. The Docker API reaches host Ollama at `host.docker.internal:11434`.

```sh
docker compose up -d postgres
```

For a new database, follow the [data setup guide](backend/docs/adrec-source-contract.md) to profile the snapshot, import it into staging, promote the prepared schemas, and configure restricted roles. The guide also explains how to inspect advisory data flags. Skip this import if your database is already populated.

The import tools and local backend checks use Python 3.11:

```sh
python3.11 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
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

Database integration tests require an explicitly disposable, populated staging database. See the [data setup guide](backend/docs/adrec-source-contract.md) for the database schema and source checks.

## License

Provided as a demonstration prototype.
