# Task Master API

FastAPI backend for Task Master.

## Setup

```bash
uv sync
uv run uvicorn task_master.main:app --reload
```

## Checks

```bash
uv run ruff format .
uv run ruff check .
uv run pyright
uv run pytest
```
