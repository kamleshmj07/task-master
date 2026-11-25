# Task Master

Goal-driven task manager to beat procrastination and achieve goals faster.

## What it does

- **Today** is the landing page. It greets you by name, shows the day at a
  glance, and holds the day's **three** tasks: only the first unfinished one
  is lit, with its next step in amber and its steps ready to tick. Free slots
  come with **suggestions** (what was left from yesterday, overdue tasks,
  tasks due that day, the next task of a quiet goal), and **Heads-up** lists
  what needs a decision. The day's routines sit beside them.
- **Goals** are outcomes worth working toward, each with a "why" and its
  progress: tasks done, days to the deadline, the next task due, and how long
  it has been quiet. Every account starts with an **Essentials** goal for
  everyday responsibilities; tasks can also have no goal. Each goal has a
  soft **colour** (picked automatically, changeable when editing), shown as a
  dot next to its tasks and on the goal filter, and as a badge and progress
  bar on its card.
- **Tasks** are broken into ordered **steps**. The first unfinished step is
  the task's next action, so every task starts with something concrete. A
  task may carry an optional **time limit**: the total time you allow for it.
  A task can **repeat** (daily, on chosen weekdays, or monthly): only the
  next run is open, and finishing or skipping it brings up the one after.
- Tasks are shown in four views: **Scheduled**, **Review** (overdue, or every
  step done but not yet completed), **Someday** (no date) and **Done**.
  Finished tasks are kept while their goal is active.
- **Postponing** is the core of the app. Moving a task later (or to Someday)
  asks why: *stuck*, *dreading*, *blocked* or *other*. Each reason gets a fix
  aimed at that root cause, and every postponement is counted. A plain edit
  cannot quietly push a date back.
- After postponing, a **tip** pops up with the fix for that reason and a link
  to its guide on the **Tips** page, which explains each reason with
  before-and-after examples.
- **Routines** are everyday chores with no goal and no steps. They repeat
  daily, weekly on chosen days, or monthly on a day of the month, between a
  start and an end date, with an optional time limit. They are ticked off per
  day and show a streak, but are never postponed. The Routines page lists
  what is due today, with a large tick, the last seven days as dots, and the
  streak, above all routines.
- **Notifications** flag goals with a deadline within a week, goals with
  every task done, goals quiet for 30 days, and tasks due in the next three
  days.
- New users are asked for their name, then **"Light the lamp"** walks them
  through four steps on Today (a goal, a task with a tiny first step, today's
  three, a routine), each lighting one ray of a desk lamp. Pages with nothing
  in them yet say what they are for and offer one way to start.
- **Settings** has the profile, Change password, and deleting the account
  with everything in it. Password fields can show what was typed.
- The look is **"First light"**: a soft graphite dark theme with warm text,
  amber for the next step only, green for done and red for overdue. A
  finished task glows once. On phones the navigation moves to a bottom tab
  bar and pop-ups slide up from the bottom.
- Security measures, what the production host must add, and known
  shortcomings are in [docs/security.md](docs/security.md).

## Structure

| Path | What | Status |
| --- | --- | --- |
| `backend/` | FastAPI API (uv project), see [`backend/README.md`](backend/README.md) | Built |
| `web/` | React + TypeScript web app (Vite, Vitest) | Built ("First light" design); Goals and Routines layout pass deferred |
| `mobile/` | Expo Android app (React Native, Jest) | Scaffold only: a placeholder screen |
| `packages/api-client/` | Typed API client shared by web and mobile, generated from the backend's OpenAPI schema | Built |
| `scripts/` | Database init SQL for Docker | |
| `docs/` | Security notes, hosting research and roadmap, Vercel guide | |
| `vercel.json`, `backend/app.py` | Vercel hosting: web and API in one project, API under `/api` | Ready, not deployed yet |

Web and mobile share logic through `packages/*`; each has its own UI.

## Development

Install pre-commit hooks from `backend/`:

```bash
cd backend
uv sync
uv run pre-commit install --config ../.pre-commit-config.yaml
```

Install the JavaScript workspace from the repo root (Node 24+):

```bash
npm install
npm run typecheck      # all workspaces
npm run lint
npm test
npm run dev -w @task-master/web
npm run android -w @task-master/mobile
```

### Run the app locally

First copy `.env.example` to `.env` (repo root) and `backend/.env`, with your
own passwords; see [`backend/README.md`](backend/README.md#setup). Then, in
three terminals, from the repo root:

```bash
docker compose up -d db                                  # Postgres
cd backend && uv run alembic upgrade head && uv run uvicorn task_master.main:create_app --factory --reload
npm run dev -w @task-master/web                          # http://localhost:5173
```

Open **http://localhost:5173**, not `127.0.0.1`: the refresh cookie needs the
web app and API (`http://localhost:8000`) on the same site. API docs are at
http://localhost:8000/docs.

To try the Tasks page with more than one page of tasks, seed a test account:
`cd backend && uv run python -m tests.seed.seed_load_more` (details in
[`backend/README.md`](backend/README.md#test-data)).

After changing API routes or schemas, regenerate the client types and commit
the result (CI fails if they are stale):

```bash
npm run generate:api
```

## Branches

`master` is the stable line. Work happens on one feature branch per page or
feature (e.g. `feature/onboarding`) and reaches `master` through a pull
request, merged once CI passes. PRs #1 to #10 are merged. Kept branches:
`hosting-readiness` (merged, PR #9) and `task-master-vercel` (the Vercel
hosting work, PR #10 merged, phases 2 onward still to do).

## CI

`.github/workflows/ci.yml` runs on every pull request and push to `master`:

- **backend**: ruff format and lint, pyright, pytest against Postgres with an
  85% coverage floor, and `pip-audit`
- **frontend**: type check, lint, tests, and `npm audit` (high and critical)
- **api-contract**: regenerates the API client and fails on any diff

`.github/workflows/uptime.yml` checks the deployed app (`/api/health` every
15 minutes, `/api/health/ready` daily). It does nothing until the repository
variables `UPTIME_CHECK=on` and `APP_URL` are set.

## Hosting

Planned on Vercel, starting on a free `vercel.app` address: the web app and
the API in one project (API under `/api`, so the sign-in cookie works), with
Neon's free Postgres. In production, rate limits and the login throttle are
shared through Postgres, so the API can run as many copies as needed.

- Decision, comparison of hosts, and the phased roadmap:
  [docs/hosting-roadmap.md](docs/hosting-roadmap.md)
- Step-by-step guide: [docs/vercel-deployment.md](docs/vercel-deployment.md)

Status: phase 1 (code) is done and merged. Next: phase 2 (GitHub workflows to
migrate then deploy, the daily clean-up, nightly backups), then accounts,
first deploy and checks.
