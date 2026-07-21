# Custodian — Back-End Build Prompt

Paste everything below this line into Claude Code (after the front end exists in the same repo).

---

Build the back end of **Custodian**, my personal wealth-management app. The React front end already exists and talks to a mock API layer in `src/api/` — read those mock functions and data shapes first and treat them as the API contract. The backend runs on a Raspberry Pi and serves the front end plus a JSON API on the same box, accessed over LAN / Tailscale (single user, me — no multi-user auth needed, but structure it so auth could be added later).

## Tech stack (non-negotiable — this is the stack I'm practicing)

- **Python 3.11+**
- **FastAPI** served by **Uvicorn**
- **PostgreSQL** as the database
- **SQLAlchemy** (2.0 style) for the ORM, with **Alembic** for migrations
- **Pydantic** models for request/response schemas
- `openpyxl`/`pandas` for parsing the Chase Excel export
- `yfinance` (or Alpha Vantage as fallback) for delayed stock quotes
- Serve the built React app as static files from FastAPI so the whole app is one service on the Pi.

## Data model

Design clean SQLAlchemy models along these lines (refine as needed, but keep the principles):

1. **Category** — id, name, kind (`income` | `expense`), sort order. Seed with: Main income, Secondary income (income); Rent, Utilities, Phone, Groceries, Dining, Transport, Subscriptions, Other (expense). Categories must be editable (add/rename/archive) via the API — the seed list is just the starting point.
2. **Transaction** — id, date, amount, description, category_id, month key (derived from date), source (`manual` | `chase_import`), import batch id (nullable). Ledger data starts at **July 2026**; reject earlier dates.
3. **Account** — id, name, type (`cash` | `stocks` | `bonds` | extensible), current balance (for cash-type accounts).
4. **Holding** — id, ticker, name, quantity, cost basis per share, purchase date, account_id. Current price is NOT stored per-request — see price feed below.
5. **PriceQuote** — ticker, price, as_of timestamp (cache table for the delayed feed).
6. **NetWorthSnapshot** — id, as_of date, total, breakdown by asset class (stocks/cash/bonds) as JSON or related rows. One snapshot per month at minimum, plus updated whenever an import is confirmed.

## Core behaviors

### 1. Monthly ledger API
CRUD endpoints for transactions scoped by month (`/api/months/{YYYY-MM}`), returning: total income, total expenses, net, and the two lists (income entries, expense entries) exactly as the front end expects.

### 2. Yearly table is derived — single source of truth
`/api/yearly-table?year=...` returns rows = months, columns = per-category totals plus total income / total expenses / net. This must be **computed by aggregation over Transaction rows at request time** (or via a view). There is no separately stored table — the monthly ledger is the single source of truth, and the yearly table can never disagree with it.

### 3. Chase import
- `POST /api/import/chase` accepts an uploaded Chase Excel/CSV export.
- Parse the standard Chase export format (columns like Transaction Date / Post Date / Description / Category / Type / Amount; be tolerant of both the credit-card and checking-account variants — detect by header row).
- Map Chase's categories to Custodian categories with a configurable mapping table; anything unmapped goes to "Other" and is flagged for review.
- Return a **preview** (parsed transactions + proposed categories + detected month) — do not write anything yet.
- `POST /api/import/chase/confirm` takes the (possibly user-edited) preview and: (a) inserts the transactions into that month's ledger tagged with an import batch id, (b) computes the **cash delta** (income − expenses from the confirmed batch), applies it to the cash account balance, and (c) updates/creates the NetWorthSnapshot for that month. This automatic net-worth roll-forward is a core feature — implement it carefully and idempotently (re-confirming the same batch must not double-count; support deleting a batch to undo).

### 4. Delayed price feed
- A quotes service that fetches ~15-minute-delayed prices for all tickers in Holdings via yfinance, cached in PriceQuote with a TTL (e.g., refresh at most every 15 minutes, and only during/near market hours).
- `/api/networth` and `/api/holdings` endpoints compute: per-holding market value, total return ($ and %), YTD return, and roll holdings + cash + bonds into total net worth and the asset-class percentage breakdown the dashboard shows.
- Must degrade gracefully offline (serve last cached quotes with their timestamp) since the Pi may lose internet.

## Non-functional requirements

- Full CORS setup for dev; in production the API and static front end share one origin.
- Config via environment variables / `.env` (database URL, API keys, port).
- Alembic migration for the initial schema + seed data script.
- Pytest tests for: the Chase parser (include sample fixture files for both export variants), the yearly-table aggregation, and the import-confirm net-worth roll-forward (including idempotency).
- Deployment notes for the Raspberry Pi: systemd unit file running Uvicorn, PostgreSQL setup commands, and how to bind so it's reachable over LAN/Tailscale.
- Keep the code idiomatic and readable — I'm using this project to get better at FastAPI/SQLAlchemy, so prefer clear structure (routers/, models/, schemas/, services/) over cleverness.
