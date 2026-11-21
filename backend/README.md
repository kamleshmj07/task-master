# Task Master API

FastAPI backend for Task Master.

## Setup

1. Copy `../.env.example` to `../.env` (for Docker) and `.env` (for the API),
   and set your own password in both.
2. Start Postgres from the repo root: `docker compose up -d db`
3. Install and migrate:

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn task_master.main:create_app --factory --reload
```

## Checks

```bash
uv run ruff format .
uv run ruff check .
uv run pyright
uv run pytest              # all tests, needs the test database
uv run pytest -m "not db"  # tests that need no database
```

## Migrations

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

## Authentication

Accounts use [fastapi-users](https://fastapi-users.github.io/fastapi-users/).
Every client sends a short-lived opaque access token (15 minutes) as
`Authorization: Bearer`. Refresh tokens last 30 days, are single use, and are
stored only as SHA-256 hashes. Reusing a spent refresh token revokes its whole
family, and changing the password logs the user out everywhere.

| Route | Purpose |
| --- | --- |
| `POST /auth/register` | Create an account |
| `POST /auth/web/login` | Log in; refresh token set as an `HttpOnly` cookie |
| `POST /auth/web/refresh` | Swap the cookie for a new access token |
| `POST /auth/web/logout` | Revoke both tokens and clear the cookie |
| `POST /auth/mobile/login` | Log in; both tokens returned in the body |
| `POST /auth/mobile/refresh` | Swap a refresh token for a new pair |
| `POST /auth/mobile/logout` | Revoke both tokens |
| `GET/PATCH /users/me` | Read or update the current account |

Register, login and refresh are rate limited per client IP
(`TASK_MASTER_AUTH_RATE_LIMIT`, default `5/minute`). Counters are in memory,
so they are per worker; move them to Redis before scaling out.

The web refresh cookie is `SameSite=Strict`, so in production the web app and
the API must share a registrable domain (e.g. `app.example.com` and
`api.example.com`).
