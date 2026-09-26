# Authentication & User Profile Module

Owner: Geeta. This module covers signup, login, logout, JWT authentication, OTP password reset, the user
profile, and user roles. Other modules use it through the contract in [Using auth from your module](#using-auth-from-your-module).

## Architecture

```text
backend/app/
├── core/                  shared foundation (used by every module)
│   ├── config.py          settings loaded from environment variables
│   ├── database.py        SQLAlchemy engine, Base, get_db, TimestampMixin
│   └── security.py        Argon2 password hashing, JWT create/decode, OTP generate/hash
├── auth/
│   ├── models.py          PasswordResetOTP
│   ├── schemas.py         request/response models + password rules
│   ├── services.py        signup, authenticate, logout, OTP request/verify, reset
│   ├── routes.py          /api/auth/* endpoints
│   ├── dependencies.py    get_current_user, CurrentUser, require_roles  ← public contract
│   ├── email.py           EmailSender interface: console (dev) / SMTP
│   └── rate_limit.py      in-process per-IP limiter for auth endpoints
├── users/
│   ├── models.py          User, UserRole
│   ├── schemas.py         UserOut, UserUpdate
│   ├── services.py        user lookups, profile update
│   └── routes.py          /api/users/me
├── models.py              imports all modules' models for Alembic
└── main.py                FastAPI app, CORS, router registration

frontend/src/
├── services/apiClient.ts  fetch wrapper: base URL, bearer token, error parsing, 401 handling
├── modules/auth/          AuthProvider/useAuth, route guards, auth API calls, validation
├── components/            layout (AppLayout sidebar with Profile menu, AuthLayout) and UI primitives
└── pages/                 Login, Signup, ForgotPassword, ResetPassword, Profile
```

**Strategy:** stateless JWT bearer tokens (HS256, `JWT_EXPIRE_MINUTES`, default 60) sent in the
`Authorization: Bearer <token>` header. Each token carries the user's `token_version`. Logout and password
reset increment it, so all tokens issued earlier stop working immediately. Logout therefore signs the
user out on every device.

The frontend keeps the token in `localStorage` so a page refresh keeps the session. It clears the token on
logout, on token expiry, on any 401 from the API, and when another tab logs out.

## User model

Table `users`:

| Column          | Type                  | Notes                                               |
|-----------------|-----------------------|-----------------------------------------------------|
| `id`            | integer PK            | use as the foreign key for audit fields             |
| `name`          | varchar(100)          | whitespace-normalised, 2–100 chars                  |
| `email`         | varchar(255), unique  | stored lower-case                                   |
| `password_hash` | varchar(255)          | Argon2id via `pwdlib`; plaintext is never stored    |
| `role`          | varchar(32)           | `INVENTORY_MANAGER` or `WAREHOUSE_STAFF`            |
| `is_active`     | boolean               | inactive users cannot log in or use tokens          |
| `token_version` | integer               | internal; bumped on logout / password reset         |
| `created_at`    | timestamptz           |                                                     |
| `updated_at`    | timestamptz           |                                                     |

Table `password_reset_otps`: `id`, `user_id` (FK → users, cascade), `otp_hash`, `expires_at`, `attempts`,
`verified_at`, `consumed_at`, `created_at`.

## Roles

| Role                | Meaning (from the brief)                                   |
|---------------------|------------------------------------------------------------|
| `INVENTORY_MANAGER` | manages incoming & outgoing stock                          |
| `WAREHOUSE_STAFF`   | performs transfers, picking, shelving and counting (default) |

- A new user chooses a role at signup. `SIGNUP_ALLOWED_ROLES` restricts which roles can be self-selected.
  For example, set it to `WAREHOUSE_STAFF` to stop anyone from signing up as a manager.
- Users **cannot** change their own role, email or active status. `PATCH /api/users/me` accepts only `name`
  and rejects any other field with 422.
- There is no admin UI for changing roles yet. Change them directly in the database if needed.

## API endpoints

All paths are prefixed with `/api` (`API_PREFIX`). Errors use FastAPI's `{"detail": ...}` shape. Validation
errors (422) return `detail` as a list of `{loc, msg}` entries.

| Method | Path                        | Auth   | Body                                                     | Success                                   |
|--------|-----------------------------|--------|----------------------------------------------------------|-------------------------------------------|
| POST   | `/api/auth/signup`          | –      | `name, email, password, confirm_password, role?`         | 201 `User`                                |
| POST   | `/api/auth/login`           | –      | `email, password`                                        | 200 `{access_token, token_type, expires_in, user}` |
| POST   | `/api/auth/logout`          | Bearer | –                                                        | 200 `{message}`; revokes all of the user's tokens |
| GET    | `/api/auth/me`              | Bearer | –                                                        | 200 `User`                                |
| POST   | `/api/auth/forgot-password` | –      | `email`                                                  | 202 `{message}` (identical for unknown emails) |
| POST   | `/api/auth/verify-otp`      | –      | `email, otp`                                             | 200 `{reset_token, expires_in}`           |
| POST   | `/api/auth/reset-password`  | –      | `reset_token, password, confirm_password`                | 200 `{message}`                           |
| GET    | `/api/users/me`             | Bearer | –                                                        | 200 `User`                                |
| PATCH  | `/api/users/me`             | Bearer | `name`                                                   | 200 `User`                                |
| GET    | `/api/health`               | –      | –                                                        | 200 `{status: "ok"}`                      |

`User` = `{id, name, email, role, is_active, created_at, updated_at}`.

Error responses:

| Status | When |
|--------|------|
| 400 | wrong/expired/used OTP; expired or already-used reset token |
| 401 | missing, invalid, expired or revoked token; wrong email or password (same message for unknown accounts) |
| 403 | inactive account; role not permitted (`require_roles`, signup allow-list) |
| 409 | signup email already registered |
| 422 | validation failure (bad email, weak password, mismatched confirmation, unknown fields) |
| 429 | per-IP rate limit exceeded on signup/login/OTP endpoints |

Password rules (enforced by both the API and the UI): 8–128 characters, at least one letter and one digit,
and no leading or trailing whitespace.

Interactive docs are available at `http://localhost:8000/docs` while the backend runs. To authorize there,
click **Authorize** and paste the `access_token`.

## OTP password reset flow

```text
/forgot-password  POST /auth/forgot-password {email}
                  → always 202 with the same message (no account enumeration)
                  → for an active account: invalidate older codes, create a 6-digit code
                    (secrets.randbelow), store only an HMAC-SHA256 of it, email it (background task)
/reset-password   POST /auth/verify-otp {email, otp}
                  → code must be the newest one, unexpired, unused, and < OTP_MAX_ATTEMPTS wrong tries
                  → success marks the code verified (it cannot be verified again) and returns a
                    reset_token (JWT, type=password_reset, PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
                  POST /auth/reset-password {reset_token, password, confirm_password}
                  → hashes the new password, marks the code consumed (the token is now single-use),
                    bumps token_version (signs out all sessions)
→ redirected to /login with a success message
```

Abuse protection:

- Codes expire after `OTP_EXPIRE_MINUTES` (default 10).
- A code is locked after `OTP_MAX_ATTEMPTS` wrong guesses (default 5).
- Only one code is valid at a time.
- Codes are resent at most once every `OTP_RESEND_COOLDOWN_SECONDS` (default 60), with at most
  `OTP_MAX_REQUESTS_PER_HOUR` per account (default 5).
- The auth endpoints allow `AUTH_RATE_LIMIT_PER_MINUTE` requests per client IP (default 20).

When a cooldown or cap applies, the endpoint still returns the same generic 202 response.

**Email delivery.** `EMAIL_BACKEND=console` is **development only**: the email, including the code, is
printed to the backend log as `[DEV EMAIL - not sent] ...`. `EMAIL_BACKEND=smtp` sends mail using the
`EMAIL_*` settings. With `ENVIRONMENT=production` the app refuses to start if the console backend or a
weak `JWT_SECRET` is configured.

## Environment variables

Backend (`backend/.env`, template in `backend/.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENVIRONMENT` | `development` | `development` / `test` / `production` (production enforces safe settings) |
| `API_PREFIX` | `/api` | URL prefix for all routes |
| `DATABASE_URL` | `postgresql+psycopg://stocksense:stocksense@localhost:5432/stocksense` | SQLAlchemy URL; `sqlite:///./stocksense.db` also works locally |
| `CORS_ORIGINS` | `http://localhost:5173` | comma-separated allowed origins |
| `JWT_SECRET` | insecure placeholder | **required**: long random secret |
| `JWT_ALGORITHM` | `HS256` | |
| `JWT_EXPIRE_MINUTES` | `60` | access token lifetime |
| `OTP_LENGTH` | `6` | digits per code |
| `OTP_EXPIRE_MINUTES` | `10` | code lifetime |
| `OTP_MAX_ATTEMPTS` | `5` | wrong guesses before a code is locked |
| `OTP_RESEND_COOLDOWN_SECONDS` | `60` | minimum gap between codes |
| `OTP_MAX_REQUESTS_PER_HOUR` | `5` | codes per account per hour |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | `10` | time to set a new password after verifying |
| `SIGNUP_ALLOWED_ROLES` | `INVENTORY_MANAGER,WAREHOUSE_STAFF` | roles selectable at signup |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `20` | per-IP limit on auth endpoints |
| `EMAIL_BACKEND` | `console` | `console` (dev only) or `smtp` |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_FROM`, `EMAIL_USE_TLS` | – | SMTP settings |

Frontend (`frontend/.env.local`, template in `frontend/.env.example`): `VITE_API_BASE_URL` (default `/api`)
and `VITE_DEV_API_PROXY_TARGET` (default `http://localhost:8000`).

## Running locally

```bash
# 1. Database (or set DATABASE_URL=sqlite:///./stocksense.db in backend/.env and skip this)
docker compose up -d db

# 2. Backend
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env              # then set JWT_SECRET
alembic upgrade head
uvicorn app.main:app --reload     # http://localhost:8000/docs

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

To try password reset locally: request a code at `/forgot-password`, then copy it from the backend
terminal (`[DEV EMAIL - not sent] ... code is: 123456`).

## Running the tests

```bash
cd backend && python -m pytest          # 66 tests: signup, login, tokens, OTP, profile, config, migrations
cd frontend && npm test                 # 16 tests: validation, route guards, login/logout, profile, reset UI
```

The backend tests use an in-memory SQLite database and a fake email sender, so neither Postgres nor
SMTP is needed. `tests/test_migrations.py` runs the real Alembic migrations on a fresh database and
then signs up and logs in against it.

## Using auth from your module

### Backend (FastAPI)

```python
from fastapi import APIRouter, Depends
from app.auth.dependencies import CurrentUser, require_roles
from app.users.models import UserRole

router = APIRouter(prefix="/products", tags=["products"])

@router.get("")
def list_products(current_user: CurrentUser):          # 401 if not signed in, 403 if inactive
    ...

@router.post("", dependencies=[Depends(require_roles(UserRole.INVENTORY_MANAGER))])
def create_product(...):                                  # 403 for other roles
    ...

@router.post("/{id}/validate")
def validate(id: int, current_user: CurrentUser):
    record.validated_by_id = current_user.id              # audit field → ForeignKey("users.id")
    if current_user.role == UserRole.INVENTORY_MANAGER: ...
```

- `current_user` is a `User` ORM object with `.id`, `.name`, `.email`, `.role` (`UserRole`) and
  `.is_active` (always `True` here; inactive users get a 403).
- For audit columns, reference users with `ForeignKey("users.id")`. Do not import auth services.
- Register your router in `app/main.py` and import your models in `app/models.py` so Alembic picks
  them up. Create your migration with `alembic revision --autogenerate -m "..."`; it will chain after
  `0001_auth`.

### Frontend (React)

```tsx
import { useAuth, ProtectedRoute } from "../modules/auth";
import { apiRequest } from "../services/apiClient";

const { user, hasRole } = useAuth();               // user.id, user.name, user.role, user.is_active
if (hasRole("INVENTORY_MANAGER")) { ... }

await apiRequest<Product[]>("/products");          // bearer token attached; a 401 signs the user out
```

- Put new pages inside the `<ProtectedRoute>` / `<AppLayout>` block in `src/App.tsx`. Use
  `<ProtectedRoute roles={["INVENTORY_MANAGER"]} />` to limit a route to certain roles.
- Add sidebar entries to a section of `NAV_SECTIONS` in `src/components/layout/AppLayout.tsx`.
- `/dashboard` is where users land after login (the Dashboard module's page, see
  [DASHBOARD.md](DASHBOARD.md)).

## Known limitations

- The rate limiter is in-memory, so its limits apply per backend process. A multi-instance deployment
  should back it with Redis.
- Tokens live in `localStorage`, which is readable by any script that runs through XSS. The short token
  lifetime and server-side revocation reduce that risk. Moving to httpOnly cookies would also require
  CSRF protection.
- Signup does not verify ownership of the email address.
