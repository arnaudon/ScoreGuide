# backend

The FastAPI service. Package name `app`, entry point `app.main:app`; it runs as a single uvicorn
worker (the table-of-contents queue and the running-completion registry live in memory).

## Modules (`app/`)

| Module | What it does |
|---|---|
| `main.py` | The app: score CRUD, PDF upload and download, the three agent endpoints, account deletion, admin settings, `/health` |
| `agent.py` | The three pydantic-ai agents, built once: `main_agent` (chat about the user's library), `imslp_agent` (SQL over the IMSLP catalogue through MCP), `complete_agent` (fills in a score, with web search and, in detailed mode, page reading) |
| `llm.py` | Model strings to pydantic-ai models (`infomaniak:…`, `google:…`), credentials from the admin page, public `GET /ai-models` |
| `sources.py` | Keeps only the links an agent's searches really returned; safe page fetching for detailed mode |
| `score_links.py` | Attaches the library scores an assistant answer talks about |
| `plans.py` | Plans, AI token metering (`metered`), storage quotas, usage reports; CLI for backfills and orphan sweeps |
| `users.py` | Auth (JWT, argon2), sign-up, email verification, password reset, demo login, admin guard |
| `uploads.py` | Who uploaded each PDF, storage used, deleting files nothing references |
| `sections.py`, `toc.py` | Table of contents: one low-priority worker thread, detection from outline, text, OCR and layout, incipit images |
| `annotations.py` | Pencil marks and notes on score pages |
| `imslp.py` | Local copy of the IMSLP catalogue (polite sync) and its search |
| `export.py` | `GET /user/export`: a ZIP of all the user's data |
| `demo.py`, `demo_texts.py` | The read-only demo account and its catalogue |
| `db.py`, `file_helper.py` | Sync and async engines (pgbouncer-safe); S3 or local storage |
| `config.py`, `rate_limit.py`, `email_utils.py` | Settings from the environment, the `slowapi` limiter, SMTP |

`migrations/` holds the Alembic migrations (schema and a few one-off data fixes).

## Commands

Run from the repository root:

```bash
uv run --frozen --directory backend pytest              # 99% coverage gate
uv run --directory backend pytest tests/test_agent.py -q  # one file
uv run --frozen ruff format --check backend
uv run --frozen ruff check backend
uv run --frozen --directory backend mypy .

./backend/scripts/run.sh                                 # dev server on :8000, --reload

uv run --directory backend alembic revision --autogenerate -m "message"
uv run --directory backend alembic upgrade head
```

Tests never call a real model: `MODEL` defaults to pydantic-ai's `"test"` model and
`ALLOW_MODEL_REQUESTS` is off.

See [`../CLAUDE.md`](../CLAUDE.md) for the architecture: SQL safety, auth, metering, storage and
deployment.
