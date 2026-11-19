# Task Master

Goal-driven task manager to beat procrastination and achieve goals faster.

## Structure

- `backend/` FastAPI API (uv project) - see `backend/README.md`
- `web/` React + TypeScript web app (planned)
- `mobile/` Expo Android app (planned)

## Development

Install pre-commit hooks from `backend/`:

```bash
cd backend
uv sync
uv run pre-commit install --config ../.pre-commit-config.yaml
```
