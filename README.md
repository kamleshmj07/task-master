# Task Master

Goal-driven task manager to beat procrastination and achieve goals faster.

## Structure

- `backend/` FastAPI API (uv project) - see `backend/README.md`
- `web/` React + TypeScript web app (Vite, Vitest)
- `mobile/` Expo Android app (React Native, Jest)
- `packages/api-client/` typed API client shared by web and mobile, generated
  from the backend's OpenAPI schema

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

After changing API routes or schemas, regenerate the client types and commit
the result (CI fails if they are stale):

```bash
npm run generate:api
```

## CI

`.github/workflows/ci.yml` runs on every pull request and push to `master`:

- **backend**: ruff format and lint, pyright, pytest against Postgres with an
  85% coverage floor, and `pip-audit`
- **frontend**: type check, lint, tests, and `npm audit` (high and critical)
- **api-contract**: regenerates the API client and fails on any diff
