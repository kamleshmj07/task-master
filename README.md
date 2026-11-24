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
  everyday responsibilities; tasks can also have no goal.
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
  day and show a streak, but are never postponed.
- **Notifications** flag goals with a deadline within a week, goals with
  every task done, goals quiet for 30 days, and tasks due in the next three
  days.
- New users are asked for their name, then **"Light the lamp"** walks them
  through four steps on Today (a goal, a task with a tiny first step, today's
  three, a routine), each lighting one ray of a desk lamp. Pages with nothing
  in them yet say what they are for and offer one way to start.
- **Settings** has the profile, Change password, and deleting the account
  with everything in it. Password fields can show what was typed.
- On phones the navigation moves to a bottom tab bar and pop-ups slide up
  from the bottom.
- Security measures, what the production host must add, and known
  shortcomings are in [docs/security.md](docs/security.md).

## Structure

| Path | What | Status |
| --- | --- | --- |
| `backend/` | FastAPI API (uv project), see [`backend/README.md`](backend/README.md) | Built |
| `web/` | React + TypeScript web app (Vite, Vitest) | Built; being redesigned page by page, Tasks page first |
| `mobile/` | Expo Android app (React Native, Jest) | Scaffold only: a placeholder screen |
| `packages/api-client/` | Typed API client shared by web and mobile, generated from the backend's OpenAPI schema | Built |
| `scripts/` | Database init SQL for Docker | |

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
request, merged once CI passes. PRs #1 to #7 are merged.

## CI

`.github/workflows/ci.yml` runs on every pull request and push to `master`:

- **backend**: ruff format and lint, pyright, pytest against Postgres with an
  85% coverage floor, and `pip-audit`
- **frontend**: type check, lint, tests, and `npm audit` (high and critical)
- **api-contract**: regenerates the API client and fails on any diff
