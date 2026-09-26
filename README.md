# StockSense — Inventory Management System

A modular inventory management system that replaces manual registers and spreadsheets with a
centralized, real-time app for Inventory Managers and Warehouse Staff.

## Tech stack

| Layer    | Stack |
|----------|-------|
| Backend  | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (SQLite works for local dev/tests), pytest |
| Frontend | React 18, TypeScript, Vite, React Router, Vitest + Testing Library |
| Auth     | JWT bearer tokens (PyJWT), Argon2 password hashing (pwdlib), OTP password reset |

## Repository layout

```text
backend/     FastAPI app (app/<module>/...), Alembic migrations, pytest suite
frontend/    React + Vite single-page app (src/modules, src/pages, src/components, src/services)
docs/        module documentation
docker-compose.yml   local PostgreSQL
```

## Quick start

```bash
docker compose up -d db                      # or use SQLite, see docs/AUTH.md

cd backend
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                         # set JWT_SECRET
alembic upgrade head
python -m app.seeds.master_data              # optional demo master data (dev only)
uvicorn app.main:app --reload                # API + docs at http://localhost:8000/docs

cd ../frontend
npm install
npm run dev                                  # http://localhost:5173
```

Tests: `cd backend && python -m pytest` and `cd frontend && npm test`.

## Modules

| Module | Owner | Docs |
|--------|-------|------|
| Authentication & User Profile | Geeta | [docs/AUTH.md](docs/AUTH.md) |
| Products & Warehouse master data | Gautam | [docs/MASTER_DATA.md](docs/MASTER_DATA.md) |
| Inventory operations & stock engine (receipts, deliveries, transfers, adjustments, stock ledger data) | Ravi Varma | [docs/INVENTORY.md](docs/INVENTORY.md) |
| Dashboard, stock availability, move history & integration | Maheshwar | [docs/DASHBOARD.md](docs/DASHBOARD.md) |

To protect an API route or a page with authentication, see
[docs/AUTH.md → Using auth from your module](docs/AUTH.md#using-auth-from-your-module).
