"""API tests for repeating tasks: runs, skipping, and changing the rule."""

from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.anyio, pytest.mark.db]

Headers = dict[str, str]

# Tests run on Sunday 2026-11-22 (FIXED_NOW in conftest).
TODAY = "2026-11-22"
DAILY: dict[str, Any] = {"frequency": "daily"}


async def create_repeating(
    client: AsyncClient, headers: Headers, **fields: Any
) -> dict[str, Any]:
    """Create a daily repeating task due today and return its JSON body."""
    payload = {
        "title": "Run 20 min",
        "steps": ["Warm up", "Run"],
        "time_limit_minutes": 30,
        "due_date": TODAY,
        "repeat": DAILY,
        **fields,
    }
    response = await client.post("/tasks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def finish(client: AsyncClient, headers: Headers, task_id: str) -> None:
    """Mark a task done."""
    response = await client.patch(
        f"/tasks/{task_id}", json={"status": "done"}, headers=headers
    )
    assert response.status_code == 200


async def open_runs(client: AsyncClient, headers: Headers) -> list[dict[str, Any]]:
    """Every open task of the user."""
    response = await client.get("/tasks", params={"status": "todo"}, headers=headers)
    return response.json()


async def skip(
    client: AsyncClient, headers: Headers, task_id: str, reason: str = "stuck"
) -> Any:
    """Skip a run and return the raw response."""
    return await client.post(
        f"/tasks/{task_id}/skip", json={"reason": reason}, headers=headers
    )


class TestCreate:
    async def test_returns_the_rule_and_a_series(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers)

        assert (task["repeat"]["frequency"], task["series_id"]) == (
            "daily",
            task["id"],
        )

    async def test_one_off_tasks_have_no_rule(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers, repeat=None)

        assert (task["repeat"], task["series_id"]) == (None, None)

    @pytest.mark.parametrize(
        "fields",
        [
            {"due_date": None},
            {"repeat": {"frequency": "weekly"}},
            {"repeat": {"frequency": "daily", "day_of_month": 3}},
            {"repeat": {"frequency": "daily", "until": "2026-11-01"}},
        ],
    )
    async def test_rejects_invalid_rules(
        self, api_client: AsyncClient, auth_headers: Headers, fields: dict[str, Any]
    ) -> None:
        payload = {"title": "Run", "steps": ["Go"], "due_date": TODAY, "repeat": DAILY}

        response = await api_client.post(
            "/tasks", json=payload | fields, headers=auth_headers
        )

        assert response.status_code == 422


class TestFinishingARun:
    async def test_creates_the_next_run_with_fresh_steps(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers)
        await api_client.patch(
            f"/tasks/{task['id']}/steps/{task['steps'][0]['id']}",
            json={"done": True},
            headers=auth_headers,
        )

        await finish(api_client, auth_headers, task["id"])

        [next_run] = await open_runs(api_client, auth_headers)
        assert (
            next_run["due_date"],
            next_run["series_id"],
            [step["done"] for step in next_run["steps"]],
            next_run["time_limit_minutes"],
        ) == ("2026-11-23", task["id"], [False, False], 30)

    async def test_reopening_and_finishing_again_adds_no_second_run(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers)
        await finish(api_client, auth_headers, task["id"])
        await api_client.patch(
            f"/tasks/{task['id']}", json={"status": "todo"}, headers=auth_headers
        )

        await finish(api_client, auth_headers, task["id"])

        assert len(await open_runs(api_client, auth_headers)) == 1

    async def test_last_run_has_no_successor(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(
            api_client, auth_headers, repeat=DAILY | {"until": TODAY}
        )

        await finish(api_client, auth_headers, task["id"])

        assert await open_runs(api_client, auth_headers) == []

    async def test_counts_toward_the_goal(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await api_client.post(
            "/goals", json={"title": "Run a marathon"}, headers=auth_headers
        )
        goal_id = goal.json()["id"]
        task = await create_repeating(api_client, auth_headers, goal_id=goal_id)

        await finish(api_client, auth_headers, task["id"])

        response = await api_client.get(f"/goals/{goal_id}", headers=auth_headers)
        progress = response.json()["progress"]
        assert (progress["done_tasks"], progress["total_tasks"]) == (1, 2)


class TestSkip:
    async def test_moves_the_run_on_and_records_why(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers)

        response = await skip(api_client, auth_headers, task["id"], "dreading")

        body = response.json()
        assert (
            response.status_code,
            body["task"]["due_date"],
            body["task"]["postpone_count"],
            body["postponement"]["reason"],
        ) == (201, "2026-11-23", 1, "dreading")

    async def test_refuses_one_off_tasks(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers, repeat=None)

        response = await skip(api_client, auth_headers, task["id"])

        assert response.status_code == 409

    async def test_refuses_the_last_run(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(
            api_client, auth_headers, repeat=DAILY | {"until": TODAY}
        )

        response = await skip(api_client, auth_headers, task["id"])

        assert response.status_code == 409

    async def test_other_needs_a_note(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers)

        response = await skip(api_client, auth_headers, task["id"], "other")

        assert response.status_code == 422

    async def test_someday_is_refused_for_repeating_tasks(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers)

        response = await api_client.post(
            f"/tasks/{task['id']}/postpone",
            json={"to_date": None, "reason": "stuck"},
            headers=auth_headers,
        )

        assert response.status_code == 409

    async def test_requires_owning_the_task(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers)

        response = await skip(api_client, other_headers, task["id"])

        assert response.status_code == 404


class TestChangingTheRule:
    async def test_a_one_off_task_can_start_repeating(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers, repeat=None)

        response = await api_client.patch(
            f"/tasks/{task['id']}",
            json={"repeat": {"frequency": "weekly", "weekdays": [6, 2, 2]}},
            headers=auth_headers,
        )

        body = response.json()
        assert (body["repeat"]["weekdays"], body["series_id"]) == ([2, 6], task["id"])

    async def test_stopping_keeps_the_series(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers)

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"repeat": None}, headers=auth_headers
        )

        body = response.json()
        assert (body["repeat"], body["series_id"]) == (None, task["id"])

    async def test_an_undated_task_cannot_repeat(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(
            api_client, auth_headers, repeat=None, due_date=None
        )

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"repeat": DAILY}, headers=auth_headers
        )

        assert response.status_code == 422

    async def test_clearing_the_date_is_refused(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_repeating(api_client, auth_headers)

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"due_date": None}, headers=auth_headers
        )

        assert response.status_code == 409
