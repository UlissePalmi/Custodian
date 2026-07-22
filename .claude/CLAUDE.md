# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Custodian is a personal wealth-management app: a monthly income/expense ledger, a derived yearly table, net worth tracking (cash/stocks/bonds), and a Chase bank-export importer that rolls confirmed imports into net worth. Single user, running on a Raspberry Pi and reached over LAN/Tailscale.

It runs as two systemd services: `custodian-frontend` (Vite, port 5173) serves the app, and `custodian` (FastAPI, port 8000) serves the JSON API. The browser calls the API cross-origin, so two settings must agree — `VITE_API_BASE_URL` in the repo root `.env` and `CORS_ORIGIN_REGEX` in `backend/.env`. `backend/deploy/DEPLOY.md` covers Pi setup, both units and day-to-day admin commands.

## Commands

Front end (repo root):
- `npm run dev` — Vite on :5173, bound to all interfaces
- `npm run typecheck` — `tsc -b --noEmit`
- `npm run build` — static bundle to `dist/`; not part of running the app, since Vite serves it
- `VITE_USE_MOCK=true npm run dev` — run against the in-memory mock, no backend or database needed

Backend (`backend/`, everything through `.venv/bin/`):
- `.venv/bin/uvicorn app.main:app --reload --port 8000` — dev server
- `.venv/bin/python -m pytest` — full suite; `-k <name>` for one test
- `.venv/bin/alembic revision --autogenerate -m "..."` then `.venv/bin/alembic upgrade head`
- `.venv/bin/python -m app.seed [--demo]` — categories, Chase mapping, empty accounts; `--demo` adds the mock's fixture data

Tests need the `custodian_test` database (they truncate it between tests — never point `TEST_DATABASE_URL` at the real one).

## Architecture

**The API contract lives in `src/api/types.ts`.** Both the mock (`src/api/mock/`) and the HTTP client (`src/api/http/client.ts`) implement the `CustodianApi` interface, and `src/api/index.ts` picks between them — components import only from there. The HTTP client's base URL comes from `VITE_API_BASE_URL`; there is no dev proxy, so requests go straight to the backend's origin. Every Pydantic schema in `backend/app/schemas/` mirrors a type in that file, so a change on one side needs the matching change on the other. Conventions: camelCase JSON, money as plain 2-dp dollar numbers, percentages as whole numbers (`12.5` = 12.5%), month keys `YYYY-MM`, transaction `amount` always positive with direction coming from `kind`.

**Two invariants shape the backend.** The monthly ledger is the single source of truth: the yearly table (`backend/app/services/yearly.py`) is aggregated from transactions at request time and never stored, so it cannot disagree with the month views. And net worth stores snapshots for *past* months only — the current month's point is recomputed live from holdings + account balances in `services/networth.py`, which is why a confirmed import moves the dashboard immediately.

**Import confirm is the one cross-cutting write** (`services/importer.py`). Uploading only parses and proposes; confirming inserts the batch's transactions, applies the batch's cash delta to the cash account, and upserts the month's snapshot — all in one database transaction. `ImportBatch.batch_id` is the primary key, which is what makes a repeated confirm collide (409) instead of double-counting; `DELETE /api/import/batches/{id}` reverses a batch using its stored `cash_delta`.

**Error messages are part of the contract.** `ApiError` (`backend/app/errors.py`) renders as `{"detail": "..."}`, the HTTP client rebuilds it as the front end's `ApiError`, and the UI shows `detail` to the user verbatim. The messages and statuses in `backend/app/services/ledger.py` match the mock's word for word — `tests/test_ledger.py` pins them.

**Shared logic is duplicated in two languages on purpose.** `backend/app/months.py` ports `src/utils/months.ts` (including `LEDGER_START`/`LEDGER_END`) and `backend/app/money.py` ports `roundCents`. Both sides round at every aggregation step so totals never drift. Extending the ledger range means editing both.

**Prices** (`services/quotes.py`) are fetched on read, cached in `price_quotes` with a 15-minute TTL, and only refreshed near US market hours. Tickers go to yfinance; a ticker that matches the ISIN pattern (e.g. a Treasury bond held as `US912810SN90`) is instead priced from three redundant German-venue JSON endpoints tried in order — Tradegate, Börse Frankfurt (an SSE stream; only the first frame is read), then onvista — which quote bonds as percent of face value, so such a holding's `quantity` is face value / 100, and it has no YTD figure. Any failure serves the cached row with its real `as_of` — the front end displays that timestamp, so a stale quote is visible rather than silently presented as live.

Backend layout is conventional: `models/` (SQLAlchemy 2.0), `schemas/` (Pydantic v2, all deriving from `CamelModel`), `services/` (all business logic), `routers/` (thin HTTP wrappers). Holdings and account balances have admin endpoints but no UI yet — they are managed with curl (see DEPLOY.md).

Front-end structure: pages in `src/pages/`, components grouped by feature in `src/components/`, data fetching through `useApi` (`src/hooks/useApi.ts`) with `useDataVersion` (`src/context/DataVersion.tsx`) as a global invalidation counter for writes that cross page boundaries, like an import. Styling is Tailwind v4 via `@tailwindcss/vite` (no config file — v4 configures in CSS). No path aliases; imports are relative.
