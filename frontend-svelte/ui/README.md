# Svelte app

The ScoreGuide UI served at [scoreguide.ch](https://scoreguide.ch): SvelteKit with Svelte 5,
Tailwind CSS 4, shadcn-svelte and Paraglide i18n (French, the base locale, plus English, German
and Italian). Built with `@sveltejs/adapter-node`.

## Layout

| Path | What it is |
|---|---|
| `src/routes/` | Pages. `+page.server.ts` loads data and runs form actions against the backend |
| `src/routes/api/` | Same-origin proxies the browser calls (PDFs, incipits, annotations, completion status, data export); they forward the session cookie as a Bearer token |
| `src/lib/components/` | App components (`ScoreViewer`, `ScoreDetailsDialog`, `AgentChat`, …) and shadcn primitives in `ui/` |
| `src/lib/server/` | Server-only helpers: `apiFetch`, `callBackend` (never throws), JWT role reading |
| `src/lib/` | Shared helpers: description rendering, metadata labels, URLs, YouTube, i18n |
| `messages/*.json` | Paraglide catalogs; every key in all four languages with the same placeholders |
| `e2e/` | Playwright tests against a stub backend (`e2e/stub-backend.mjs`) |

## Backend and auth

The session JWT lives in an httpOnly `access_token` cookie. Server code calls the backend at
`BACKEND_URL` with that token as a Bearer header; the layout reads the role from the token only
as a UI hint, and the backend checks every request. A Content-Security-Policy is generated with
nonces (`vite.config.ts`); fonts are self-hosted.

## Commands

```bash
npm ci
npm run dev          # dev server on :3000
npm run build        # production build (also generates src/lib/paraglide/)
node build           # run the production build
npm run check        # svelte-check
npm run lint         # prettier + eslint
npx vitest --run     # unit tests: node and browser (Chromium) projects
npx playwright test  # end-to-end tests
```

CI runs all of them (`.github/workflows/test.yml`); `frontend.yml` is a faster build and
node-test check.
