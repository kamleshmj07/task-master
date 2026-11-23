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

## Code layout

| Path | What |
| --- | --- |
| `src/task_master/main.py` | App factory: middleware and routers |
| `src/task_master/config.py` | Settings from `TASK_MASTER_*` env vars or `.env` |
| `src/task_master/models.py` | SQLAlchemy models |
| `src/task_master/schemas.py` | Request and response schemas |
| `src/task_master/routes/` | One module per resource |
| `src/task_master/auth/` | Accounts, tokens, login throttling |
| `src/task_master/postponement.py` | The fix suggested for each postpone reason |
| `src/task_master/routines.py` | When routines are due, and streaks |
| `src/task_master/cleanup.py` | Deletes finished tasks past retention |
| `src/task_master/openapi.py` | Writes the OpenAPI schema for client generation |
| `migrations/` | Alembic migrations |
| `tests/` | pytest suite, mirroring `src/`; `tests/seed/` holds test-data scripts |

## API

Every route below needs a signed-in user and only ever touches that user's
data: another user's goal, task or routine is reported as `404`. Lists take
`limit` (max 100, default 50) and `offset`. Full, interactive docs are at
`/docs` outside production.

| Route | Purpose |
| --- | --- |
| `GET/POST /goals`, `GET/PATCH/DELETE /goals/{id}` | Goals; deleting one deletes its tasks |
| `GET/POST /tasks`, `GET/PATCH/DELETE /tasks/{id}` | Tasks; filter by `view`, `status`, `someday`, `goal_id`, `no_goal` |
| `GET /tasks/counts` | Totals per view (Scheduled, Review, Someday, Done) for the same goal filters |
| `POST /tasks/{id}/steps`, `PATCH/DELETE /tasks/{id}/steps/{step_id}` | Add, rename, tick or remove steps; a task keeps at least one |
| `PUT /tasks/{id}/steps/order` | Reorder all of a task's steps |
| `POST /tasks/{id}/postpone` | Move a task later or to Someday with a reason; returns the suggested fix |
| `GET /tasks/{id}/postponements` | A task's postponement history |
| `GET/POST /routines`, `GET/PATCH/DELETE /routines/{id}` | Routines |
| `GET /routines/due?on=` | Routines due on a day, with done flag and streak |
| `PUT/DELETE /routines/{id}/completions/{day}` | Tick a routine off for a day, or undo it |
| `GET/PUT /plans/{date}` | A day's Top 3 tasks, shown beside its routines |
| `POST /notifications/check` | Create any notifications now due, return the unread count; called when the app opens |
| `GET /notifications`, `GET /notifications/unread-count` | Notifications, newest first |
| `POST /notifications/{id}/read`, `POST /notifications/read-all` | Mark notifications as read |
| `DELETE /users/me` | Delete the account and all its data; needs the current password |

Each open task is in exactly one view: **Review** if every step is done or
its due date has passed, otherwise **Scheduled** (dated) or **Someday**
(undated). The fix returned by `/postpone` is shown once by the client and is
not stored. Notifications cover goal deadlines within 7 days, goals whose tasks
are all done, goals quiet for 30 days, and one daily summary of tasks due in
the next 3 days; each event is notified once.

A task's due date can be brought forward with `PATCH`, but moving it later or
clearing it must go through `/postpone`, so every deferral is recorded.

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
| `GET/PATCH /users/me` | Read or update the current account (display name, timezone) |

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
them together with their steps, postponements and plan slots. Read
notifications older than that are deleted too; unread ones and open tasks are
never deleted. Run it once a day from cron, Windows Task Scheduler or your
platform's scheduler:

```bash
uv run python -m task_master.cleanup
```

## Test data

With the API running locally, seed a test account
(`loadmore-test@example.com` / `correct-horse-battery`) with 56 scheduled and
4 Someday tasks, enough to show "Load more" on the Tasks page:

```bash
uv run python -m tests.seed.seed_load_more
uv run python -m tests.seed.seed_load_more --scheduled 80 --someday 10 --email other@example.com
```

It only talks to a local API and refuses any other host.
