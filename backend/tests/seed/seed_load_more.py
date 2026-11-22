"""Create a test account with enough tasks to show "Load more" on the Tasks page.

Talks to a running local API, so the data goes through the same validation
as the app. Re-running adds another batch to the same account.

Usage, from `backend/` with the API running:

    uv run python -m tests.seed.seed_load_more
    uv run python -m tests.seed.seed_load_more --scheduled 80 --someday 10
"""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx

DEFAULT_API = "http://localhost:8000"
DEFAULT_EMAIL = "loadmore-test@example.com"
DEFAULT_PASSWORD = "correct-horse-battery"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
OVERDUE_DAYS = 3
DESCRIPTION = "Seed a local test account with enough tasks to show Load more."


@dataclass(frozen=True)
class Options:
    """What to create, and where."""

    api: str
    email: str
    password: str
    scheduled: int
    someday: int
    today: date


def parse_args(argv: Sequence[str]) -> Options:
    """Read command-line options; exits with status 2 on bad input."""
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--api", default=DEFAULT_API, help="local API base URL")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--scheduled", type=_count, default=56, help="dated tasks")
    parser.add_argument("--someday", type=_count, default=4, help="undated tasks")
    args = parser.parse_args(argv)
    if httpx.URL(args.api).host not in LOCAL_HOSTS:
        parser.error(f"refusing to seed a non-local API: {args.api}")
    return Options(
        api=args.api,
        email=args.email,
        password=args.password,
        scheduled=args.scheduled,
        someday=args.someday,
        today=date.today(),
    )


def seed(client: httpx.Client, options: Options) -> dict[str, Any]:
    """Register (or reuse) the account, add the tasks, return the task counts."""
    headers = _sign_in(client, options)
    goal_id = _default_goal_id(client, headers)
    for index in range(options.scheduled):
        due = options.today + timedelta(days=index - OVERDUE_DAYS)
        _create_task(client, headers, f"Scheduled task {index + 1:02d}", due, goal_id)
    for index in range(options.someday):
        _create_task(client, headers, f"Someday idea {index + 1}", None, None)
    counts: dict[str, Any] = client.get("/tasks/counts", headers=headers).json()
    return counts


def main(argv: Sequence[str] | None = None) -> int:
    """Run the seed; returns 0 on success and 1 if the API refuses a request."""
    options = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        with httpx.Client(base_url=options.api, timeout=10) as client:
            counts = seed(client, options)
    except httpx.HTTPError as error:
        print(f"Seeding failed: {error}", file=sys.stderr)
        return 1
    print(f"Seeded {options.email}: {counts}")
    return 0


def _count(value: str) -> int:
    number = int(value)
    if not 0 <= number <= 500:
        raise argparse.ArgumentTypeError("must be between 0 and 500")
    return number


def _sign_in(client: httpx.Client, options: Options) -> dict[str, str]:
    """Register the account if it is new, then log in; return auth headers."""
    client.post(
        "/auth/register",
        json={"email": options.email, "password": options.password},
    )
    login = client.post(
        "/auth/mobile/login",
        data={"username": options.email, "password": options.password},
    )
    login.raise_for_status()
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _default_goal_id(client: httpx.Client, headers: dict[str, str]) -> str | None:
    response = client.get("/goals", headers=headers)
    response.raise_for_status()
    goals: list[dict[str, Any]] = response.json()
    return next((g["id"] for g in goals if g["title"] == "Essentials"), None)


def _create_task(
    client: httpx.Client,
    headers: dict[str, str],
    title: str,
    due: date | None,
    goal_id: str | None,
) -> None:
    response = client.post(
        "/tasks",
        headers=headers,
        json={
            "title": title,
            "steps": ["First step", "Second step"],
            "due_date": due.isoformat() if due else None,
            "goal_id": goal_id,
            "time_limit_minutes": 30,
        },
    )
    response.raise_for_status()


if __name__ == "__main__":
    sys.exit(main())
