"""Vercel entrypoint: the API app, built from `TASK_MASTER_*` settings.

The root `vercel.json` runs this module as the backend service. On Vercel the
API is served under `/api`, so set `TASK_MASTER_API_PREFIX=/api` there.
"""

from task_master.main import create_app

app = create_app()
