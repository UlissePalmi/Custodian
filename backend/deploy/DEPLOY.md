# Deploying Custodian on the Raspberry Pi

Custodian runs as two services:

| Service | Port | What it is |
| --- | --- | --- |
| `custodian` | 8000 | FastAPI — the JSON API, nothing else |
| `custodian-frontend` | 5173 | Vite serving the React app |

Open the app at **`http://<pi-address>:5173`**. The browser loads the page from
5173 and then calls the API on 8000 directly, which is a cross-origin request —
hence the two settings that have to agree:

* `VITE_API_BASE_URL` in the repo root `.env` tells the front end where the API is.
* `CORS_ORIGIN_REGEX` in `backend/.env` tells the API which origins may call it.

## 1. PostgreSQL

```bash
sudo apt install -y postgresql
sudo -u postgres psql -c "CREATE USER custodian WITH PASSWORD 'custodian';"
sudo -u postgres createdb -O custodian custodian
sudo -u postgres createdb -O custodian custodian_test   # only needed to run the tests
```

The database listens on localhost only, which is what we want — nothing but the
API talks to it.

## 2. Backend

```bash
cd ~/Documents/Custodian/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then edit DATABASE_URL if you changed the password
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed  # categories, Chase mapping, empty Cash/Bonds/Brokerage accounts
```

Add `--demo` to the seed command to load the front end's fixture data instead of
starting empty. Only useful for comparing the API against the mock.

## 3. Front end

```bash
cd ~/Documents/Custodian
npm install
cp .env.example .env    # set VITE_API_BASE_URL to this Pi's address
```

No build step: the Vite service compiles on the fly and hot-reloads when you
edit. `npm run build` is only needed if you ever want a static bundle.

## 4. Run both as services

```bash
cd ~/Documents/Custodian/backend/deploy
sudo cp custodian.service custodian-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now custodian custodian-frontend
systemctl status custodian custodian-frontend
```

Logs: `journalctl -u custodian -f` (or `-u custodian-frontend`).

## If the Pi's address changes

The front end's API URL is fixed in the root `.env`, so it needs updating:

```bash
nano ~/Documents/Custodian/.env          # VITE_API_BASE_URL=http://<new-address>:8000/api
sudo systemctl restart custodian-frontend
```

`CORS_ORIGIN_REGEX` matches port 5173 on any host, so it does not need changing —
this also means reaching the app over a Tailscale name works as soon as
`VITE_API_BASE_URL` points at the Tailscale address.

## Day-to-day

Recording what you own — there is no UI for holdings or balances yet:

```bash
# Set the cash and bonds balances (account ids come from GET /api/accounts)
curl -X PUT localhost:8000/api/accounts/1 -H 'Content-Type: application/json' \
     -d '{"balance": 28450}'

# Add a position
curl -X POST localhost:8000/api/holdings -H 'Content-Type: application/json' \
     -d '{"ticker":"VOO","name":"Vanguard S&P 500 ETF","quantity":42,"costBasisPerShare":465.20}'

curl localhost:8000/api/holdings
```

Undoing a Chase import (reverses its transactions and its cash movement):

```bash
curl -X DELETE localhost:8000/api/import/batches/<batchId>
```

## Development

The services already run both halves, and Vite hot-reloads front-end edits, so
usually there is nothing to start. To run them by hand instead:

```bash
sudo systemctl stop custodian custodian-frontend
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
npm run dev     # in the repo root
```

`VITE_USE_MOCK=true npm run dev` runs the front end against the in-memory mock
with no backend or database at all.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```

They use the `custodian_test` database and truncate it between tests, so never
point `TEST_DATABASE_URL` at the real one.

## Notes

* Price quotes come from yfinance (tickers) or, for holdings entered by ISIN,
  from Tradegate → Börse Frankfurt → onvista, first venue to answer wins.
  Quotes are cached for 15 minutes and only refreshed near US market hours.
  If the Pi is offline the last cached price is served with its real
  timestamp, which the dashboard displays. ISIN prices are percent of face
  value, so enter such a holding's quantity as face value / 100.
* The ledger starts in July 2026 and the month picker ends in December 2027.
  Extending it means changing `LEDGER_END` in both `backend/app/months.py` and
  `src/utils/months.ts`.
