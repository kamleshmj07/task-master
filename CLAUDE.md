# Task Master: project context

Goal-driven task manager to beat procrastination. Read this first when
picking up development. Shared rules (uv only, anyio tests, commit message
style, `ArthurClune` as PR reviewer, security and testing rules) live in
`C:\dev\CLAUDE.md` and `C:\dev\.claude\rules\`; this file adds what is
specific to this repo.

## Working agreements with the user

- Never start servers, commit, or push unless asked in that turn.
- Redesign the UI **page by page, flow by flow**. The Tasks page is done; the
  others (Today, Routines, Goals, Settings, then mobile) follow and should
  reuse its pieces (`Modal`, `TaskCard`, the step checklist, chips).
- Show a **mockup first** for UI redesigns (a Design canvas artifact worked
  well), and agree on open design questions before building.
- Keep replies short. Ask only for real decisions; recommend an option.
- The `frontend-design` plugin is installed; use it for new UI work.

## Stack and layout

| Path | What |
| --- | --- |
| `backend/` | FastAPI, async SQLAlchemy 2.1 + asyncpg, Alembic, fastapi-users, Python 3.14 (uv) |
| `web/` | React 19 + TypeScript (strict) + Vite, tests with Vitest, Testing Library, axe-core |
| `mobile/` | Expo SDK 58, jest-expo. **Placeholder screen only** |
| `packages/api-client/` | openapi-fetch client; `src/schema.ts` is generated from the backend |
| `.github/workflows/ci.yml` | backend, frontend and api-contract jobs; runs on PRs and pushes to `master` |

npm workspaces (pnpm is not installed). Postgres 17 in Docker on
`127.0.0.1:5434`, with a `task_master_test` database for tests.

## Everyday commands

```bash
docker compose up -d db
cd backend && uv run alembic upgrade head
uv run uvicorn task_master.main:create_app --factory --reload --host localhost --port 8000
npm run dev -w @task-master/web -- --host localhost --port 5173   # from repo root
```

- Open **http://localhost:5173**, never `127.0.0.1`: the refresh cookie is
  `SameSite=Strict` and needs web and API on the same site.
- Checks: `uv run ruff format . && uv run ruff check . && uv run pyright &&
  uv run pytest --cov-fail-under=85` in `backend/`; `npm run typecheck && npm run
  lint && npm test` at the root.
- After any API change: `npm run generate:api` and commit `openapi.json` and
  `schema.ts` (CI fails on drift).
- Test accounts on the dev DB (password `correct-horse-battery`):
  `loadmore-test@example.com` (60 tasks, for Load more) and
  `smoke-test@example.com`. Re-seed with
  `cd backend && uv run python -m tests.seed.seed_load_more`.
- Clean-up job (not yet scheduled anywhere): `uv run python -m task_master.cleanup`.

## Domain rules (decided with the user)

- **Goals** are optional on tasks and routines. Every new user gets an
  ordinary, deletable **"Essentials"** goal (`defaults.py`).
- **Tasks** have an ordered list of **steps** (at least 1, at most 50). The
  first unfinished step is `next_step`. Ticking the last step never completes
  the task; the UI asks "All steps done. Mark complete?".
- **Time limit** (`time_limit_minutes`, optional) is the total time allowed
  for a task. No timer, no tracking. There is **no daily capacity**.
- **Views**, decided on the server, each task in exactly one:
  **Review** (open and overdue, or every step done), **Scheduled** (dated,
  today or later), **Someday** (no date), **Done** (kept 90 days, then the
  clean-up job deletes it). Lists page 50 at a time; `/tasks/counts` gives
  real totals.
- **Postponing** asks for a reason: `stuck`, `dreading`, `blocked`, or
  `other` (which needs a note of up to 280 characters). It moves the date
  later or to Someday (`to_date: null`), counts towards `postpone_count`, and
  returns a suggested fix (`postponement.py`); the third `blocked` adds "is it
  really time, or dread?". The fix is also saved as a **notification**.
  `PATCH /tasks/{id}` refuses to move a date later or clear it, so nothing
  skips postponement. Moving a date earlier is a plain edit and is not logged.
- **Routines** repeat daily, weekly on chosen weekdays, or monthly on a day
  (29th to 31st fall back to the month's last day), between a required start
  and end date. Ticked per day with a streak; never postponed; never in the
  Top 3.
- **Top 3**: ranked one-off tasks for a day (today or later), shown beside
  the day's routines (`/plans/{date}`).
- **Notifications**: only postpone tips for now; bell with unread badge, mark
  read or all read.
- **Account**: `display_name` is asked on first sign-in (welcome dialog,
  cannot be skipped). `DELETE /users/me` with the current password deletes
  everything the user owns.
- **Auth**: opaque bearer access tokens (15 minutes). Web keeps the rotating
  refresh token in an `HttpOnly` cookie scoped to `/auth/web`; mobile gets it
  in the body. Reusing a refresh token revokes its family. Failed logins are
  throttled per account (backoff from 1 to 15 minutes) and per IP (20 per 15
  minutes). Password reset and email verification are not built (no email
  provider yet).

## Visual design: "Desk lamp" (approved 2026-11-23)

Tokens live at the top of `web/src/index.css`; mockup on the canvas
artifact (artboard "Tasks page – Desk lamp direction").

- Blue-slate room (`--ink #161a24`, `--slate #1f2533`), warm paper text
  (`--paper #ece6d9`). One lamp: amber `--lamp #f2b544` marks **only** the
  next step and keyboard focus. Green = done, red = overdue or lost.
- Primary buttons are paper-filled with ink text, never amber.
- One family: Atkinson Hyperlegible Next; tabular figures; sentence case.
- Corners by role: dialogs 16px, panels 12px, controls 8px, chips pill.
- Tasks are rows in one panel per group with a status rail (red overdue,
  green every step done); the next step is the large amber line. Steps form a
  numbered trail (real sequence). One motion: the new next step glows once.
- Copy rules: no middle-dot joins, no ALL-CAPS labels, no arrows glued to text.
- Done for the shell and Tasks page; Today, Routines and Goals inherit the
  tokens but still need their own layout pass.

## Code conventions learned here

- Line endings are LF (`.gitattributes`). On Windows, write files from
  Python with `encoding="utf-8", newline="\n"`, or cp1252 and CRLF creep in.
- Inject time through `NowDep` / `get_now`; API tests pin it to
  2026-11-22 12:00 UTC (`tests/conftest.py`). Use `local_today(tz, now)`
  for the user's date.
- Ownership: look rows up with `get_owned_or_404` (other users' rows are
  404, never 403).
- Migrations are hand-written when check constraints change (autogenerate
  misses them); use `op.f()` for names, and copy constants into migrations
  rather than importing app code. `test_models_match_migrations` guards parity.
- SQL NULL trap: `NULL < today` is NULL and `~NULL` stays NULL, so guard
  nullable columns in view conditions.
- Web: shared helpers go in `data.ts` / `dates.ts`, not component files
  (fast-refresh lint). Tests mock `@/api` with `vi.mock(..., await import(...))`.

## Status (2026-11-23)

- Branch `feature/auth-and-tooling`, pushed to GitHub, 16 commits ahead of
  `master` at `3681955`. **No pull request yet, so CI has never run.**
- Dev database migrated to `c2e193cd6125` (head).
- Tests: 383 backend (98% coverage), 99 web, 3 api-client, all passing.

## Next steps (ask the user which first)

1. Open a PR into `master` (reviewer `ArthurClune`) so CI runs; then use one
   short-lived branch per page or feature.
2. User testing of the redesigned Tasks page, notifications and Settings.
3. Redesign the remaining pages, mockup first: Today, Routines, Goals.
4. Schedule the clean-up job daily.
5. Move login throttling counters to Redis and configure uvicorn's trusted
   proxy before running several workers.
6. Mobile UI (shares `packages/api-client`; own screens).
7. Later: email provider for password reset and verification; more
   notification kinds if wanted.
