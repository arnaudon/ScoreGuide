# ScoreGuide

A personal library for your sheet music, with an AI that knows the pieces.

**Live:** [scoreguide.ch](https://scoreguide.ch) (there is a read-only demo on the login page)

Upload your PDF scores and ScoreGuide reads them like a music stand: page turns, a table of
contents of the pieces and movements it finds, pencil marks and notes. An AI fills in what you
would like to know before playing a piece (history, playing tips, anecdotes, with the sources it
found), and an assistant helps you choose what to play from your library or from the IMSLP
catalogue.

## Features

- **Library**: PDF upload, details per score (composer, year, period, genre, form, key,
  difficulty…), search and sort.
- **AI completion**: a sectioned description in English and French (History, Playing it, Did you
  know?, Sources). Every link is checked against what the AI's web searches really returned.
- **Reader**: music-stand PDF viewer with an automatic table of contents, annotations and notes.
- **Assistant**: chat about your own library, or search the IMSLP catalogue in plain language.
- **Accounts**: plans with AI tokens and storage, email verification, data export (ZIP) and
  account deletion.
- **Four languages**: French, English, German and Italian.
- **Privacy**: everything is hosted in Switzerland by Infomaniak, including the AI models; see
  [the privacy page](https://scoreguide.ch/privacy).

## Stack

| Part | Technology |
|---|---|
| Frontend | SvelteKit (Svelte 5), Tailwind CSS 4, shadcn-svelte, Paraglide i18n |
| Backend | Python, FastAPI, SQLModel, Alembic |
| AI | pydantic-ai agents on Infomaniak AI Services (open models), DuckDuckGo search, MCP for SQL |
| Data | PostgreSQL behind pgbouncer, S3-compatible storage for PDFs |
| Ops | Docker Compose on an Infomaniak VPS, Caddy, GitHub Actions, Sentry |

## Repository layout

| Path | What it is |
|---|---|
| [`backend/`](backend/) | FastAPI service: API, agents, auth, plans, table-of-contents jobs |
| [`shared/`](shared/) | SQLModel tables and response models used by the backend |
| [`frontend-svelte/ui/`](frontend-svelte/ui/) | The SvelteKit app served at scoreguide.ch |
| `infrastructure/` | Terraform and setup script for the VPS, the read-only SQL role |
| `caddy/`, `postgres-init/` | Reverse proxy config, database bootstrap |

Architecture notes (agents, SQL safety, auth, metering, storage, deployment) are in
[`CLAUDE.md`](CLAUDE.md).

## Development

Prerequisites: [`uv`](https://docs.astral.sh/uv/), Docker with Compose, Node 22 or newer.

```bash
# Full stack: backend on :8000, Svelte on :3000, Postgres, MCP sidecar
docker compose up --build

# Backend only (uvicorn --reload, local SQLite)
./backend/scripts/run.sh

# Frontend only
cd frontend-svelte/ui && npm ci && npm run dev
```

Without AI credentials the agents use pydantic-ai's test model. Real models are set on the admin
page (`infomaniak:<model>` or `google:<model>`), with their API keys.

## Tests and checks

CI runs all of these on every pull request (`.github/workflows/`):

```bash
# Python, per workspace member (backend, shared); backend coverage gate: 99%
uv sync --frozen
uv run --frozen --directory backend pytest
uv run --frozen ruff format --check backend
uv run --frozen ruff check backend
uv run --frozen --directory backend mypy .

# Svelte
cd frontend-svelte/ui
npm run build && npm run check && npm run lint
npx vitest --run          # node and browser (Chromium) projects
npx playwright test       # end-to-end, against a stub backend
```

Migrations:

```bash
uv run --directory backend alembic revision --autogenerate -m "message"
uv run --directory backend alembic upgrade head
```

API docs: `http://localhost:8000/docs` when the backend runs.

## Deployment

Every push to `main` deploys: GitHub Actions connects to the VPS, writes the secrets into `.env`,
rebuilds the containers and runs the migrations. See [`CLAUDE.md`](CLAUDE.md#deployment).

## License

[GPL-3.0](LICENSE).
