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
