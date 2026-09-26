# StockSense — Inventory Management System

StockSense replaces manual registers and spreadsheets with one centralized, real-time inventory app
for **Inventory Managers** and **Warehouse Staff**.

## Features

- **Authentication:** signup, login and logout. JWT sessions revoke server-side on logout and password
  reset. Passwords can be reset with a one-time code (OTP). Includes a profile page and two roles
  (Inventory Manager, Warehouse Staff).
- **Product management:** products with SKU, category, unit of measure and optional initial stock;
  categories; units of measure; reordering rules. SKU search and filters.
- **Warehouse management:** multiple warehouses, each with locations (racks, shelves, zones).
- **Receipts:** incoming goods from suppliers; validating adds stock.
- **Delivery orders:** confirm → pick → pack → validate; validating removes stock and never oversells.
- **Internal transfers:** move stock between locations or warehouses; total stock is unchanged.
- **Inventory adjustments:** record a physical count; stock is set to the counted quantity.
- **Dashboard:** KPIs (products in stock, low/out of stock, pending receipts, pending deliveries,
  scheduled transfers) with filters by document type, status, warehouse, location and category.
- **Stock ledger / Move History:** every stock change with product, quantity, from/to, document, user
  and time.
- **Low-stock visibility:** in-stock, low-stock and out-of-stock status per product and location, based
  on reordering rules.

## Tech stack

| Layer | Stack |
|-------|-------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (SQLite also works for local dev and tests) |
| Frontend | React 18, TypeScript, Vite, React Router |
| Auth | JWT bearer tokens (PyJWT), Argon2 password hashing (pwdlib) |
| Tests | pytest (backend), Vitest + Testing Library (frontend) |

## Repository layout

```text
backend/
  app/            one package per module: auth, users, categories, units, warehouses, locations,
                  products, reorder_rules, inventory (stock engine + ledger), receipts, deliveries,
                  transfers, adjustments, dashboard; shared code in app/core
  alembic/        database migrations (0001 auth → 0002 master data → 0003 inventory)
  tests/          pytest suite (auth, master_data/, inventory/, dashboard/)
  .env.example    backend configuration template
frontend/
  src/            modules/ (API clients, hooks, shared module components), pages/, components/
  .env.example    frontend configuration template
docs/             per-module documentation
docker-compose.yml  local PostgreSQL
```

There is one backend, one frontend, one database, one authentication system, one stock table (the
source of truth) and one stock movement ledger.

## Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer (tested with Node 22)
- PostgreSQL 14 or newer, either via Docker (`docker compose`) or installed locally. SQLite works for a
  quick local run.

## Setup

### 1. Database

```bash
docker compose up -d db        # PostgreSQL 16 on localhost:5432, user/password/db: stocksense
```

To use SQLite instead, skip this step and set `DATABASE_URL=sqlite:///./stocksense.db` in `backend/.env`.

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate                 # Windows;  macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                   # then set JWT_SECRET (see below)
alembic upgrade head                   # create/upgrade the schema
python -m app.seeds.master_data        # optional demo data, development only
uvicorn app.main:app --reload          # API on http://localhost:8000, docs at /docs
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                            # http://localhost:5173, forwards /api to the backend
```

Open http://localhost:5173 and sign in with the demo account (created by the seed script above; also shown
at the bottom of the login page in development):

- **Email:** `admin@stocksense.com`
- **Password:** `Admin1234`

Or sign up. Choose **Inventory Manager** to be able to create master data; every signed-in user can run
inventory operations.

### Production build

```bash
cd frontend
npm run build                          # type-check + bundle into frontend/dist
npm run preview                        # serve the build locally (also forwards /api)
```

In production, serve `frontend/dist` as static files and send `/api` requests to the backend, e.g.
`uvicorn app.main:app --host 0.0.0.0 --port 8000` behind a reverse proxy. Set `ENVIRONMENT=production`:
the backend then refuses to start with a weak `JWT_SECRET` or the development console email backend.

## Environment variables

Backend (`backend/.env`; every variable with its default is in `backend/.env.example`, details in
[docs/AUTH.md](docs/AUTH.md#environment-variables)):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | e.g. `postgresql+psycopg://stocksense:stocksense@localhost:5432/stocksense` |
| `JWT_SECRET` | **required**: long random value (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) |
| `JWT_EXPIRE_MINUTES` | access token lifetime (default 60) |
| `CORS_ORIGINS` | allowed browser origins, comma-separated (default `http://localhost:5173`) |
| `ENVIRONMENT` | `development` / `test` / `production` |
| `EMAIL_BACKEND`, `EMAIL_*` | `console` (dev: OTP codes are printed in the backend log) or `smtp` |
| `OTP_*`, `SIGNUP_ALLOWED_ROLES`, `AUTH_RATE_LIMIT_PER_MINUTE` | password reset and abuse limits |

Frontend (`frontend/.env.local`, optional): `VITE_API_BASE_URL` (default `/api`) and
`VITE_DEV_API_PROXY_TARGET` (default `http://localhost:8000`).

Never commit `.env` files; they are git-ignored.

## Migrations

```bash
cd backend
alembic upgrade head          # apply all migrations
alembic current               # show the current revision
alembic downgrade -1          # roll back one migration
alembic revision --autogenerate -m "describe change"   # after changing models (import them in app/models.py)
```

## Demo data

`python -m app.seeds.master_data` adds a demo Inventory Manager login (`admin@stocksense.com` /
`Admin1234`), one category (Raw Materials), two units (Kilogram, Piece) and a
Main Warehouse (`DEMO-MAIN`) with Rack A and Rack B. All of it is labelled as demo data. The script is
safe to run repeatedly and refuses to run with `ENVIRONMENT=production`. Products and stock are created
through the app.

A typical walkthrough:
1. Create a product.
2. Receive 100 units into Rack A.
3. Transfer 30 to Rack B.
4. Deliver 20 from Rack B (confirm → pick → pack → validate).
5. Adjust Rack B to its counted quantity.
6. Check the Dashboard and Move History.

## Tests

```bash
cd backend && python -m pytest      # 259 tests; in-memory SQLite per test
cd frontend && npm test             # 65 tests
```

To run the backend suite against PostgreSQL (the target database), point it at an empty database.
Everything in that database is wiped.

```bash
TEST_DATABASE_URL=postgresql+psycopg://stocksense:stocksense@localhost:5432/stocksense_test python -m pytest
```

Highlights:
- `tests/dashboard/test_end_to_end.py` runs the full receive → transfer → deliver → adjust flow through
  the API and checks stock, dashboard and ledger.
- `tests/inventory/test_concurrency.py` validates competing deliveries from real threads. On PostgreSQL
  this exercises the row locks.

## How the modules fit together

```text
Auth (users, JWT) ──▶ every API endpoint and page requires a signed-in user
Master data ──▶ products, categories, units, warehouses → locations, reorder rules
Inventory engine ──▶ receipts / deliveries / transfers / adjustments
      └─ validate: one DB transaction = status change + stock update + stock_movements rows
Dashboard ──▶ reads stock, documents, reorder rules and the ledger (read-only, aggregated in SQL)
```

Stock changes **only** when a document is validated. Validation is idempotent (repeating it changes
nothing), all or nothing for multi-line documents, and safe under concurrent requests.

| Module | Owner | Docs |
|--------|-------|------|
| Authentication & User Profile | Geeta | [docs/AUTH.md](docs/AUTH.md) |
| Products & Warehouse master data | Gautam | [docs/MASTER_DATA.md](docs/MASTER_DATA.md) |
| Inventory operations & stock engine | Ravi Varma | [docs/INVENTORY.md](docs/INVENTORY.md) |
| Dashboard, stock availability, move history & integration | Maheshwar | [docs/DASHBOARD.md](docs/DASHBOARD.md) |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| First page load after `npm run dev` is blank for a few seconds | Vite compiles on the first request; wait or reload. |
| Every API call fails with "The server ran into a problem" (dev server) or "The server is not reachable right now" (behind a reverse proxy) | The backend is not running where the frontend forwards `/api`. Start `uvicorn` (port 8000), or set `VITE_DEV_API_PROXY_TARGET`. |
| Backend exits with `JWT_SECRET must be set ...` | `ENVIRONMENT=production` requires a random `JWT_SECRET` of 32+ characters and `EMAIL_BACKEND=smtp`. |
| `connection refused` on `alembic upgrade head` | The database is not reachable; check `DATABASE_URL` and that `docker compose up -d db` is running. |
| `docker compose up` fails with "port is already allocated" | Another PostgreSQL is running locally; stop it or map a different host port in `docker-compose.yml` and update `DATABASE_URL`. |
| Password reset: where is the code? | With `EMAIL_BACKEND=console` (development) the code is printed in the backend log (`[DEV EMAIL - not sent] ... code is: 123456`). |
| "Too many requests" on login | The per-IP limit (`AUTH_RATE_LIMIT_PER_MINUTE`, default 20/min) was hit; wait a minute. |
| Start over with an empty database | SQLite: delete the `.db` file. PostgreSQL: `alembic downgrade base && alembic upgrade head`. Then re-run the seed. |
| Signed out unexpectedly | Tokens expire after `JWT_EXPIRE_MINUTES` (default 60) and are revoked on logout or password reset; sign in again. |

## Known limitations

- The login rate limiter keeps its counts in memory, so the limit applies per backend process. Use a
  shared store before running several instances.
- Stock is not reserved when an order is confirmed or picked; availability is enforced when it is
  validated. There is no negative stock, backordering or unit conversion.
- Suppliers and customers are free-text fields on documents; there is no directory.
- Signup does not verify ownership of the email address.
