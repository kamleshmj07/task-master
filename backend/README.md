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

Failed logins are throttled; successful ones never are:

- **Per account**: the first 4 failures are free. The 5th locks the account
  for 1 minute, and each further failure doubles the lock (2, 4, 8, up to
  15 minutes). A successful login clears the count, and so do 15 quiet
  minutes. While locked, the password is not even checked.
- **Per IP**: 20 failures in 15 minutes, across all accounts, block that IP.

Both answer `429` with `Retry-After`, and unknown emails are throttled
exactly like real ones, so the lockout never reveals which accounts exist.
Locks are always temporary, so nobody can lock a real user out for good.
Tune with the `TASK_MASTER_LOGIN_*` settings in `config.py`.

Register and refresh keep a simple per-IP limit
(`TASK_MASTER_AUTH_RATE_LIMIT`, default `5/minute`).

All counters live in memory, so they are per worker and reset on restart;
move them to Redis before scaling out.

The web refresh cookie is `SameSite=Strict`, so in production the web app and
the API must share a registrable domain (e.g. `app.example.com` and
`api.example.com`).

## Clean-up job

Finished tasks stay under Done for 90 days
(`TASK_MASTER_COMPLETED_TASK_RETENTION_DAYS`), then a clean-up job deletes
them together with their steps, postponements and plan slots. Open tasks are
never deleted. Run it once a day from cron, Windows Task Scheduler or your
platform's scheduler:

```bash
uv run python -m task_master.cleanup
```
