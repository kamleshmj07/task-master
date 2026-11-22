"""Smoke tests for the load-more seed script, against a fake API."""

import json
from datetime import date
from typing import Any

import httpx
import pytest

from tests.seed import seed_load_more
from tests.seed.seed_load_more import Options, parse_args, seed

TODAY = date(2026, 11, 22)


class FakeApi:
    """Records task creations and answers like the real API."""

    def __init__(self, login_status: int = 200) -> None:
        self.login_status = login_status
        self.tasks: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/auth/register":
            return httpx.Response(201, json={})
        if path == "/auth/mobile/login":
            return httpx.Response(self.login_status, json={"access_token": "t"})
        if path == "/goals":
            return httpx.Response(200, json=[{"id": "g1", "title": "Essentials"}])
        if path == "/tasks/counts":
            dated = sum(task["due_date"] is not None for task in self.tasks)
            undated = len(self.tasks) - dated
            return httpx.Response(
                200, json={"scheduled": dated, "someday": undated, "done": 0}
            )
        self.tasks.append(json.loads(request.content))
        return httpx.Response(201, json={})


def options(scheduled: int = 3, someday: int = 2) -> Options:
    return Options(
        api="http://localhost:8000",
        email="seed@example.com",
        password="correct-horse-battery",
        scheduled=scheduled,
        someday=someday,
        today=TODAY,
    )


def run_seed(api: FakeApi, opts: Options) -> dict[str, Any]:
    transport = httpx.MockTransport(api)
    with httpx.Client(transport=transport, base_url=opts.api) as client:
        return seed(client, opts)


class TestSeed:
    def test_creates_the_requested_tasks(self) -> None:
        counts = run_seed(FakeApi(), options(scheduled=3, someday=2))

        assert counts == {"scheduled": 3, "someday": 2, "done": 0}

    def test_starts_three_days_overdue_then_one_a_day(self) -> None:
        api = FakeApi()

        run_seed(api, options(scheduled=2, someday=0))

        assert [task["due_date"] for task in api.tasks] == ["2026-11-19", "2026-11-20"]

    def test_dated_tasks_use_the_default_goal(self) -> None:
        api = FakeApi()

        run_seed(api, options(scheduled=1, someday=1))

        assert [task["goal_id"] for task in api.tasks] == ["g1", None]

    def test_every_task_has_steps(self) -> None:
        api = FakeApi()

        run_seed(api, options())

        assert all(task["steps"] for task in api.tasks)


class TestParseArgs:
    def test_defaults_to_more_than_one_page(self) -> None:
        opts = parse_args([])

        assert (opts.scheduled > 50, opts.api) == (True, "http://localhost:8000")

    def test_reads_counts(self) -> None:
        opts = parse_args(["--scheduled", "80", "--someday", "10"])

        assert (opts.scheduled, opts.someday) == (80, 10)

    @pytest.mark.parametrize(
        "argv",
        [
            ["--api", "https://api.example.com"],
            ["--scheduled", "-1"],
            ["--scheduled", "501"],
            ["--someday", "many"],
        ],
    )
    def test_rejects_bad_input(self, argv: list[str]) -> None:
        with pytest.raises(SystemExit) as exit_info:
            parse_args(argv)

        assert exit_info.value.code == 2


class TestMain:
    def test_returns_1_when_login_fails(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        transport = httpx.MockTransport(FakeApi(login_status=400))
        real_client = httpx.Client
        monkeypatch.setattr(
            seed_load_more.httpx,
            "Client",
            lambda **kwargs: real_client(transport=transport, **kwargs),  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
        )

        assert seed_load_more.main([]) == 1
        assert "Seeding failed" in capsys.readouterr().err
