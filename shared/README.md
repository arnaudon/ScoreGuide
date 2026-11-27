# shared

SQLModel tables and pydantic models used by the backend (and its migrations). Importable as
`shared.<module>`.

## Modules

| Module | Contents |
|---|---|
| `shared.user` | `User` table: account, role (`user`, `admin`, `demo`), plan, music profile, preferences |
| `shared.scores` | `Score` (library), `IMSLP` (catalogue copy), `ScoreSection` and `TocReport` (table of contents), `ScoreCreate` / `ScoreUpdate` request models and their text limits |
| `shared.metadata` | The fixed vocabulary for genre and form, `Mixed` keys, and the normalizers every write goes through |
| `shared.annotations` | Pencil marks and notes on score pages |
| `shared.uploads` | Who uploaded each stored PDF, and its size |
| `shared.usage` | `AIUsage`: one row per agent run or token grant, the source of truth for allowances |
| `shared.settings` | `Setting` key/value table (models, model weights, plan limits, credentials) |
| `shared.responses` | What the agent endpoints return |

## Checks

From the repository root, as CI runs them:

```bash
uv run --frozen --directory shared pytest
uv run --frozen ruff check shared
uv run --frozen ruff format --check shared
uv run --frozen --directory shared mypy .
```
