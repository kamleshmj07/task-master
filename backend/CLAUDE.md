# Backend notes

Loaded when working under `backend/`. Project-wide context is in `../CLAUDE.md`.

## Code conventions

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
