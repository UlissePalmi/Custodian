# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Custodian is a personal wealth-management app: a monthly income/expense ledger, a derived yearly table, net worth tracking (cash/stocks/bonds), and Plaid bank sync that pulls transactions in automatically and rolls them into net worth. Single user, running on a Raspberry Pi and reached over Tailscale.

It runs as two systemd services: `custodian-frontend` (Vite, port 5173) serves the app, and `custodian` (FastAPI, port 8000) serves the JSON API. In deployment both sit behind `tailscale serve`, which terminates HTTPS on 443 and proxies `/` to Vite and `/api` to FastAPI — required for Plaid's OAuth redirect, and it makes the two same-origin so CORS and mixed-content rules stop applying to normal traffic. The services themselves are unchanged by this: still separate processes on their own ports, still directly reachable. `VITE_API_BASE_URL` (`frontend/.env`) points at the proxied HTTPS API; `CORS_ORIGIN_REGEX` (`backend/.env`) still governs direct cross-origin access to :8000. `backend/deploy/DEPLOY.md` covers Pi setup, both units and day-to-day admin commands.

## Commands

Front end (`frontend/`):
- `npm run dev` — Vite on :5173, bound to all interfaces
- `npm run typecheck` — `tsc -b --noEmit`
- `npm run build` — static bundle to `dist/`; not part of running the app, since Vite serves it
- `VITE_USE_MOCK=true npm run dev` — run against the in-memory mock, no backend or database needed

Backend (`backend/`, everything through `.venv/bin/`):
- `.venv/bin/uvicorn app.main:app --reload --port 8000` — dev server
- `.venv/bin/python -m pytest` — full suite; `-k <name>` for one test
- `.venv/bin/alembic revision --autogenerate -m "..."` then `.venv/bin/alembic upgrade head`
- `.venv/bin/python -m app.seed [--demo]` — categories, Plaid category mapping, empty accounts; `--demo` adds the mock's fixture data

Tests need the `custodian_test` database (they truncate it between tests — never point `TEST_DATABASE_URL` at the real one).

## Architecture

**The API contract lives in `frontend/src/api/types.ts`.** Both the mock (`frontend/src/api/mock/`) and the HTTP client (`frontend/src/api/http/client.ts`) implement the `CustodianApi` interface, and `frontend/src/api/index.ts` picks between them — components import only from there. The HTTP client's base URL comes from `VITE_API_BASE_URL`, which points at the `tailscale serve` HTTPS address; there is no Vite dev proxy. Every Pydantic schema in `backend/app/schemas/` mirrors a type in that file, so a change on one side needs the matching change on the other. Conventions: camelCase JSON, money as plain 2-dp dollar numbers, percentages as whole numbers (`12.5` = 12.5%), month keys `YYYY-MM`, transaction `amount` always positive with direction coming from `kind`.

**Two invariants shape the backend.** The monthly ledger is the single source of truth: the yearly table (`backend/app/services/yearly.py`) is aggregated from transactions at request time and never stored, so it cannot disagree with the month views. And net worth stores snapshots for *past* months only — the current month's point is recomputed live from holdings + account balances in `services/networth.py`, which is why a sync moves the dashboard immediately.

**A Plaid sync is the one cross-cutting write** (`services/plaid_sync.py`). It inserts the batch's transactions, applies their combined cash delta to the cash account, and upserts every touched month's snapshot — all in one database transaction, alongside advancing the item's sync cursor, so a crash re-fetches rather than skips. There is no review step, which puts the weight on not double-counting: `Transaction.plaid_transaction_id` guards a re-sync, `services/dedup.py` guards against manually entered duplicates, and matched transfer pairs (a card payment seen from both linked accounts) are dropped rather than counted as income and expense. `services/batches.delete_batch` reverses a batch using its stored `cash_delta`, exposed as `DELETE /api/import/batches/{id}`.

The Chase PDF/CSV importer this replaced is gone; `chase_import` survives only as a legacy `Transaction.source` value.

**Error messages are part of the contract.** `ApiError` (`backend/app/errors.py`) renders as `{"detail": "..."}`, the HTTP client rebuilds it as the front end's `ApiError`, and the UI shows `detail` to the user verbatim. The messages and statuses in `backend/app/services/ledger.py` match the mock's word for word — `tests/test_ledger.py` pins them.

**Shared logic is duplicated in two languages on purpose.** `backend/app/months.py` ports `src/utils/months.ts` (including `LEDGER_START`/`LEDGER_END`) and `backend/app/money.py` ports `roundCents`. Both sides round at every aggregation step so totals never drift. Extending the ledger range means editing both.

**Prices** (`services/quotes.py`) are fetched on read, cached in `price_quotes` with a 15-minute TTL, and only refreshed near US market hours. Tickers go to yfinance; a ticker that matches the ISIN pattern (e.g. a Treasury bond held as `US912810SN90`) is instead priced from three redundant German-venue JSON endpoints tried in order — Tradegate, Börse Frankfurt (an SSE stream; only the first frame is read), then onvista — which quote bonds as percent of face value, so such a holding's `quantity` is face value / 100, and it has no YTD figure. Any failure serves the cached row with its real `as_of` — the front end displays that timestamp, so a stale quote is visible rather than silently presented as live.

**Accounts are mapped to real bank accounts, and the bank owns the balance** (`models/account.py`, `services/reconcile.py`). `Account.plaid_account_id` binds one to a Plaid account, and every sync writes what the bank reports into `balance`. A locally accumulated balance provably cannot track the account it names: every transaction's cash effect lands on one account (`networth.get_cash_account`), so card spending moved the checking balance, and transfers are excluded as internal though each really does leave checking. Transactions therefore no longer move balances at all — `networth.apply_cash_effect` is a no-op for mapped accounts and every caller goes through it. A brokerage is the one exception in shape: its `balance` is only *uninvested cash*, since `current` counts positions too and would double them. Unmapped accounts (a foreign bank) stay manual and are never touched.

**The reconciliation check asks whether the ledger saw everything that moved** (`models/balance_checkpoint.py`). Per-account drift became structurally impossible once balances came from the bank, so each sync records a `BalanceCheckpoint`: `tracked_total` (connected cash − card debt + brokerage cash + positions **at cost**) against `ledger_net` (cumulative income − expenses). Cost rather than market is load-bearing — a price move is not a transaction, and a purchase only converts cash into holdings of equal value, so neither disturbs the figure. The offset between the two is a meaningless constant; a *change* in it means money moved without an entry. `GET /api/plaid/reconciliation` and the timer's `BALANCE DRIFT` line report only changes.

An account's balance does not always count under its own name. A `credit`-type account holds what is *owed*, stored positive and subtracted from cash — net worth is assets minus debts. A `stocks`-type account's balance is its *uninvested* cash, which counts as cash rather than stocks: it is not exposed to the market, so counting it as stocks would overstate that exposure. Only the account's `holdings` count as stocks. `accounts_breakdown` therefore returns one row per (account, asset class) pair — a brokerage with idle cash yields two — each carrying `asset_class` alongside `type`, so the page groups the same way the dashboard slices and the two can never disagree. `services/networth.accounts_breakdown` reproduces exactly these rules for `GET /api/accounts/breakdown`, which backs the allocation page — the two views must sum to the same total or one of them is lying.

**Holdings have two owners** (`services/plaid_investments.py`). Positions in a linked brokerage are `source='plaid'` and replaced wholesale on every sync — holdings are state, not a stream of events, so a sell simply stops being reported. Anything Plaid cannot see (a Treasury bought direct) is `source='manual'` and never touched by a sync; without that split a synced and a hand-entered row for the same security would double the position. Cash-like rows Plaid reports inside a brokerage (a sweep fund, an unsettled balance) are skipped: they are money in the account, not securities, and have no ticker the price feed could quote.

Backend layout is conventional: `models/` (SQLAlchemy 2.0), `schemas/` (Pydantic v2, all deriving from `CamelModel`), `services/` (all business logic), `routers/` (thin HTTP wrappers). Account balances and manual holdings have admin endpoints but no UI yet — they are managed with curl (see DEPLOY.md).

Front-end structure: pages in `src/pages/`, components grouped by feature in `src/components/`, data fetching through `useApi` (`src/hooks/useApi.ts`) with `useDataVersion` (`src/context/DataVersion.tsx`) as a global invalidation counter for writes that cross page boundaries, like a sync. Styling is Tailwind v4 via `@tailwindcss/vite` (no config file — v4 configures in CSS). No path aliases; imports are relative.
