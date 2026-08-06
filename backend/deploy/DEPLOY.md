# Deploying Custodian on the Raspberry Pi

Custodian runs as two services:

| Service | Port | What it is |
| --- | --- | --- |
| `custodian` | 8000 | FastAPI — the JSON API, nothing else |
| `custodian-frontend` | 5173 | Vite serving the React app |

Open the app at **`http://<pi-address>:5173`**. The browser loads the page from
5173 and then calls the API on 8000 directly, which is a cross-origin request —
hence the two settings that have to agree:

* `VITE_API_BASE_URL` in `frontend/.env` tells the front end where the API is.
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
.venv/bin/python -m app.seed  # categories, Plaid category mapping, empty Cash/Bonds/Brokerage accounts
```

Add `--demo` to the seed command to load the front end's fixture data instead of
starting empty. Only useful for comparing the API against the mock.

## 3. Front end

```bash
cd ~/Documents/Custodian/frontend
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

## 5. Plaid bank sync

Pulls transactions from your banks on a schedule and posts them straight to
the ledger — this is how transactions get in. The app still runs without it
configured; you just enter everything by hand.

### 5a. HTTPS via `tailscale serve`

Plaid's OAuth handoff with Chase requires an HTTPS redirect URI, and this app
is otherwise reached over plain HTTP. `tailscale serve` terminates TLS on 443
and reverse-proxies to both services exactly as they already run — no cert
files to manage, no application or port changes, and Tailscale renews the
certificate itself.

```
https://<pi-name>.<tailnet>.ts.net/       → Vite     (127.0.0.1:5173)
https://<pi-name>.<tailnet>.ts.net/api/   → FastAPI  (127.0.0.1:8000)
```

Routing both halves under one hostname also makes them same-origin, which is
why nothing here touches CORS: the browser stops applying cross-origin and
mixed-content rules that would otherwise block an HTTPS page calling an HTTP
API. The services stay separate processes on their own ports; only the
browser-facing URL is unified.

First enable **HTTPS Certificates** for the tailnet at
<https://login.tailscale.com/admin/dns> (free; requires MagicDNS). Without it
`tailscale serve` hangs trying to obtain a certificate it isn't allowed to
get. Note that each certified machine name is published permanently to the
public Certificate Transparency log — the name only, which resolves to a
non-routable `100.x` address.

```bash
sudo tailscale serve --bg --set-path /api http://127.0.0.1:8000/api
sudo tailscale serve --bg http://127.0.0.1:5173
tailscale serve status          # both routes, "tailnet only"
```

Then point the front end at the proxied API and restart it:

```bash
nano ~/Documents/Custodian/frontend/.env   # VITE_API_BASE_URL=https://<pi-name>.<tailnet>.ts.net/api
sudo systemctl restart custodian-frontend
```

The serve config lives in tailscaled's state and survives reboots — no extra
systemd unit. To undo it entirely: `tailscale serve reset`.

Use `serve`, never `funnel` — `funnel` publishes to the whole internet, and
Custodian has no authentication of its own.

Verify:

```bash
curl -s https://<pi-name>.<tailnet>.ts.net/api/health     # {"status":"ok"}
```

Then open `https://<pi-name>.<tailnet>.ts.net` in a browser and confirm the
data loads with no console errors. If hot-reload stops working (websocket
errors in the console only — the app itself is fine), add
`server.hmr: { clientPort: 443, protocol: 'wss' }` to `frontend/vite.config.ts`.

After this the app is reachable only from devices on the tailnet; plain-LAN
access without Tailscale no longer works.

### 5b. Plaid credentials

Get a client id and secret from the [Plaid dashboard](https://dashboard.plaid.com);
the free Trial plan covers a single-user app's transaction sync at no cost.
Add to `backend/.env`:

```
PLAID_CLIENT_ID=...
PLAID_SECRET=...
PLAID_ENV=sandbox        # switch to production once you're ready to link the real account
PLAID_REDIRECT_URI=https://<pi-name>.<tailnet>.ts.net/
PLAID_TOKEN_ENCRYPTION_KEY=...   # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`PLAID_REDIRECT_URI` must exactly match a redirect URI registered in the
Plaid dashboard. Test against `PLAID_ENV=sandbox` first — Plaid's default
sandbox institutions don't redirect at all (log in with `user_good` /
`pass_good`, MFA code `1234`), so you can validate the link → sync → reverse
flow before spending a real Production Item on it. Plaid also offers *OAuth*
sandbox institutions, which do exercise the redirect round-trip — worth
linking one before going to production.

A sandbox access token is not valid in production. Disconnect any sandbox
connection (`DELETE /api/plaid/items/{itemId}`, or the sidebar's Disconnect)
before switching `PLAID_ENV`, otherwise its stored item fails on every sync.

```bash
cd ~/Documents/Custodian/backend
.venv/bin/pip install -r requirements.txt   # adds plaid-python, cryptography
.venv/bin/alembic upgrade head
sudo systemctl restart custodian
```

Then open the app, click **Connect a bank** (sidebar on desktop, the bank icon
in the header on mobile), and complete Plaid Link. Link every card you use:
purchases on an unlinked card are invisible, and a payment to it then counts as
spending, whereas a payment between two linked accounts is recognised as a
transfer and excluded from the ledger.

### 5c. The sync timer

```bash
cd ~/Documents/Custodian/backend/deploy
sudo cp custodian-plaid-sync.service custodian-plaid-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now custodian-plaid-sync.timer
systemctl list-timers custodian-plaid-sync.timer
```

Runs hourly and catches up on the next boot if the Pi was offline. Logs:
`journalctl -u custodian-plaid-sync -f`. Trigger a sync immediately instead of
waiting for the timer: `sudo systemctl start custodian-plaid-sync.service`.

Unlinking a connection (`DELETE /api/plaid/items/{itemId}`, or "Disconnect" in
the sidebar) stops future syncs but leaves past transactions in the ledger —
that's a separate action:

```bash
curl -X DELETE localhost:8000/api/import/batches/<batchId>   # reverses one sync's transactions
```

## If the Pi's address changes

The front end's API URL is fixed in `frontend/.env`, so it needs updating:

```bash
nano ~/Documents/Custodian/frontend/.env          # VITE_API_BASE_URL=http://<new-address>:8000/api
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

Undoing a sync batch (reverses its transactions and its cash movement):

```bash
curl -X DELETE localhost:8000/api/import/batches/<batchId>
```

## Development

The services already run both halves, and Vite hot-reloads front-end edits, so
usually there is nothing to start. To run them by hand instead:

```bash
sudo systemctl stop custodian custodian-frontend
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
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
