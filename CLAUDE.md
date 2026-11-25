# Task Master: project context

Goal-driven task manager to beat procrastination. Read this first when
picking up development. Shared rules (uv only, anyio tests, commit message
style, security and testing rules) live in
`C:\dev\CLAUDE.md` and `C:\dev\.claude\rules\`; this file adds what is
specific to this repo.

## Working agreements with the user

- Never start servers, commit, or push unless asked in that turn.
- Never create a branch on your own: suggest one, say what it would be based
  on, and wait for the OK. Branching from unmerged work mixes features into
  one PR, so say so when that would happen.
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
- Stopping the web dev server's `npm run dev` leaves Vite's `node` child
  listening on 5173. After stopping it, check the port and end that
  `vite.js` process by PID.

## Domain rules (decided with the user)

- **Goals** are optional on tasks; routines never have one. Every goal
  response carries `progress` (tasks done of total, next task due, last moved);
  the web shows days to the deadline and "quiet for N days" (30+) from it.
  Deleting a goal deletes its tasks (never routines), always behind an in-app
  confirmation that says how many. Every new user gets an
  ordinary, deletable **"Essentials"** goal (`defaults.py`).
- **Tasks** have an ordered list of **steps** (at least 1, at most 50). The
  first unfinished step is `next_step`. Ticking the last step never completes
  the task; the UI asks "All steps done. Mark complete?".
- **Time limit** (`time_limit_minutes`, optional) is the total time allowed
  for a task. No timer, no tracking. There is **no daily capacity**.
- **Views**, decided on the server, each task in exactly one:
  **Review** (open and overdue, or every step done), **Scheduled** (dated,
  today or later), **Someday** (no date), **Done**. Finished tasks are kept
  while their goal is active; goal-less ones, and those of goals completed or
  archived more than 90 days ago, are deleted by the clean-up job. Lists page 50 at a time; `/tasks/counts` gives
  real totals.
- **Postponing** asks for a reason: `stuck`, `dreading`, `blocked`, or
  `other` (which needs a note of up to 280 characters). It moves the date
  later or to Someday (`to_date: null`), counts towards `postpone_count`, and
  returns a suggested fix (`postponement.py`); the third `blocked` adds "is it
  really time, or dread?". The fix appears once as a **tip pop-up** that
  links to its guide on the **Tips** page; it is not stored anywhere and is
  gone once acknowledged.
  `PATCH /tasks/{id}` refuses to move a date later or clear it, so nothing
  skips postponement. Each task carries `postponement_reasons` (counts per
  reason); the web shows "Postponed 3 times: 2 blocked, 1 dreading", and the
  full history only when asked ("Show postponement history").
- A finished task's steps are read-only: no adding, removing, reordering or
  ticking. Top 3 tasks on Today expand to the same step checklist. Moving a date earlier is a plain edit and is not logged.
- **Repeating tasks** (`repeats.py`) are recurring goal work ("Run 20 min
  every day"): a task with a `repeat` rule (daily, weekly on chosen days, or
  monthly; optional `until`). Only one run is open at a time. Finishing a run
  creates the next, with fresh steps, on the first due day after it that is
  not in the past (missed runs are not owed). Runs share `series_id`; done
  runs count in goal progress. A run cannot go to Someday; instead
  `POST /tasks/{id}/skip` moves it to the next due day, with a reason, and
  counts as a postponement.
- **Routines** are independent chores: no goal, no steps (decided). They
  have an optional time limit (each time due), and repeat
  daily, weekly on chosen weekdays, or monthly on a day
  (29th to 31st fall back to the month's last day), between a required start
  and end date. Ticked per day with a streak; never postponed; never in the
  Top 3.
- **Today** (landing page, redesigned 2026-11-24; mockup on the "Task
  Master – Today" canvas): a greeting by name, the day at a glance, the day's
  three with only the first open task lit (next step in amber, its steps open
  to tick), routines with streaks, and Heads-up. `/plans/{date}` also returns
  `suggestions` while a slot is free (left from yesterday, overdue, due that
  day, next task of the quietest goals; at most 6) and, for today only,
  `heads_up` (overdue, every step done, due within 3 days; at most 5;
  nothing already in the three) (`day_guide.py`). Unfinished tasks are
  suggested the next morning, never carried over automatically.
- **First-run setup, "Light the lamp"** (`routes/onboarding.py`,
  `LightTheLamp.tsx`): a card on Today with four steps done in place (a goal
  of their own, a task with a tiny first step, a pick for the three, a
  routine). Each lights one ray of a desk lamp. Progress is read from the
  user's data; only `onboarded_at` is stored, set by "Start my day". "Not
  now" hides it for the day (browser storage). Accounts that had tasks
  before were marked set up by the migration. Tasks, Goals and Routines
  have empty states with one sentence and one button.
- **Notifications** (`alerts.py`), created when the app opens
  (`POST /notifications/check`, safe to repeat; each event has a unique
  `key`):
  - an active goal's deadline is within 7 days (once per deadline)
  - every task under an active goal is done (once per latest completion)
  - an active goal has not moved for 30 days: no edit, new task, task
    change or step tick (once per quiet spell). Essentials is included on
    purpose (decided 2026-11-24): a quiet Essentials means the app fell out
    of use
  - one summary a day when open tasks are due in the next 3 days
  Each opens Goals or Tasks from the bell. Tips are never stored.
- **Account**: `display_name` is asked on first sign-in (welcome dialog,
  cannot be skipped). `DELETE /users/me` with the current password deletes
  everything the user owns.
- **Auth**: opaque bearer access tokens (15 minutes). Web keeps the rotating
  refresh token in an `HttpOnly` cookie scoped to `/auth/web`; mobile gets it
  in the body. Reusing a refresh token revokes its family. Failed logins are
  throttled per account (backoff from 1 to 15 minutes) and per IP (20 per 15
  minutes). Password reset and email verification are not built (no email
  provider yet). Changing the email or password needs `current_password`;
  Settings has a Change password form (signs out everywhere afterwards).
  Password re-checks (email or password change, account deletion) pause for
  24 hours after 5 wrong passwords in a row (`auth/reauth.py`).
- **Security hardening** (`security.py`, details in `docs/security.md`):
  security headers on every response (HSTS in production), API-wide rate
  limits per session or IP (reads and writes separately), JSON security logs
  without personal data (`logging_setup.py`), trusted proxies via
  `TASK_MASTER_TRUSTED_PROXIES`, no OpenAPI schema in production, and
  production refuses to start without HTTPS CORS origins and a 32+ character
  secret.
- **Single API process (decided 2026-11-24, a known shortcoming).** Rate
  limit and throttle counters live in memory, so production holds a Postgres
  advisory lock and a second process refuses to start (`single_process.py`).
  Redis would lift this. Open concern, parked by the user until the end of
  the production-readiness work: zero-downtime deploys start the new version
  before stopping the old one, so the new one may refuse to start. Either the
  host stops the old version first, or the new process waits for the lock.

## Visual design and code conventions

- The "Desk lamp" visual design rules live in `web/CLAUDE.md`. Read it
  before any mockup or UI work, even when no web file is open yet.
- Backend conventions (time injection, ownership lookups, migrations, the
  SQL NULL trap) live in `backend/CLAUDE.md`.
- Line endings are LF (`.gitattributes`). On Windows, write files from
  Python with `encoding="utf-8", newline="\n"`, or cp1252 and CRLF creep in.

## Status (2026-11-24, end of session)

- `master` has everything so far: PR #1 (MVP) at `1b21d97` and PR #2 (Tasks
  page polish, Tips page, notifications) at `bcce44a`, both merged after CI
  passed. The old feature branches are deleted.
- PR #3 (Phase 1) merged at `b9b938a`; its branch is kept for now (user
  will clean up later). PR #4 (security hardening) merged at `f6e62ba`.
  PR #5 (Today redesign) merged at `f5528de`, PR #6 (onboarding, show
  password) at `0a21dfa`, PR #7 (phone layout) at `e3df4ea`. No active
  branch: the checkout is on `master`. Merged feature branches are kept on
  purpose (the user will clean them up). Before any new work, suggest a
  branch and wait for the user's OK. Each branch reaches `master` through a
  PR, merged once CI passes.
- PRs are opened without a reviewer for now: the reviewer rule in
  `C:\dev\.claude\rules\backend.md` is temporarily switched off.
- Dev database migrated to `674ce9fdd30a` (head).
- Tests: 517 backend (98% coverage), 210 web, 3 api-client, all passing.

## Next steps (ask the user which first)

1. Deployment (start here): pick a host first (a short comparison was
   offered), then: app container, production config, HTTPS, the web headers
   in `docs/security.md`; schedule the clean-up job; backups; monitoring.
2. Email provider for password reset and verification (also fixes sign-up
   revealing taken emails).
3. Parked security findings, to decide together before launch (also in
   memory): the 24-hour password re-check pause can trap an intruder in;
   the single API process and zero-downtime deploys.
4. End-to-end browser tests (Playwright).
5. Later: a fuller Goals and Routines layout pass; the mobile app (shares
   `packages/api-client`); premium features (postponement insights, weekly
   review, LLM review).
