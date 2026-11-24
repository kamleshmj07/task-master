"""API tests for Today's suggestions and heads-up. "Today" is 2026-11-22."""

from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.anyio, pytest.mark.db]

Headers = dict[str, str]
TODAY = "2026-11-22"
YESTERDAY = "2026-11-21"


async def task(
    client: AsyncClient, headers: Headers, title: str, **fields: Any
) -> dict[str, Any]:
    """Create a task and return its JSON body."""
    payload = {"title": title, "steps": ["Start"], **fields}
    response = await client.post("/tasks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def plan(client: AsyncClient, headers: Headers, day: str = TODAY) -> Any:
    """The plan response for `day`."""
    response = await client.get(f"/plans/{day}", headers=headers)
    return response.json()


async def set_plan(
    client: AsyncClient, headers: Headers, day: str, task_ids: list[str]
) -> None:
    """Pick the Top 3 for `day`."""
    response = await client.put(
        f"/plans/{day}", json={"task_ids": task_ids}, headers=headers
    )
    assert response.status_code == 200, response.text


def kinds(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(kind, task title) per suggestion or heads-up item."""
    return [(item["kind"], item["task"]["title"]) for item in items]


class TestSuggestions:
    async def test_puts_overdue_before_due_today(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await task(api_client, auth_headers, "Due today", due_date=TODAY)
        await task(api_client, auth_headers, "Late", due_date="2026-11-20")

        body = await plan(api_client, auth_headers)

        assert kinds(body["suggestions"])[:2] == [
            ("overdue", "Late"),
            ("due_today", "Due today"),
        ]

    async def test_offers_the_day_befores_unfinished_three_first(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await task(api_client, auth_headers, "Late", due_date="2026-11-20")
        left = await task(api_client, auth_headers, "Left over")
        # Past plans cannot be set, so plan tomorrow and look at the day after.
        await set_plan(api_client, auth_headers, "2026-11-23", [left["id"]])

        body = await plan(api_client, auth_headers, "2026-11-24")

        first = body["suggestions"][0]
        assert (first["kind"], first["task"]["title"], first["previous_rank"]) == (
            "left_over",
            "Left over",
            1,
        )

    async def test_leaves_out_tasks_already_in_the_three(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        late = await task(api_client, auth_headers, "Late", due_date="2026-11-20")
        await set_plan(api_client, auth_headers, TODAY, [late["id"]])

        body = await plan(api_client, auth_headers)

        assert "Late" not in [title for _, title in kinds(body["suggestions"])]

    async def test_suggests_the_next_task_of_a_goal(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await api_client.post(
            "/goals", json={"title": "Run a marathon"}, headers=auth_headers
        )
        await task(api_client, auth_headers, "Buy shoes", goal_id=goal.json()["id"])

        body = await plan(api_client, auth_headers)

        [suggestion] = [s for s in body["suggestions"] if s["kind"] == "goal_next"]
        assert (suggestion["task"]["title"], suggestion["goal_title"]) == (
            "Buy shoes",
            "Run a marathon",
        )

    async def test_none_once_three_are_picked(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        ids = [
            (await task(api_client, auth_headers, f"T{n}", due_date=TODAY))["id"]
            for n in range(4)
        ]
        await set_plan(api_client, auth_headers, TODAY, ids[:3])

        body = await plan(api_client, auth_headers)

        assert body["suggestions"] == []

    async def test_none_for_past_days(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await task(api_client, auth_headers, "Late", due_date="2026-11-20")

        body = await plan(api_client, auth_headers, YESTERDAY)

        assert body["suggestions"] == []

    async def test_at_most_six(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        for n in range(8):
            await task(api_client, auth_headers, f"T{n}", due_date=TODAY)

        body = await plan(api_client, auth_headers)

        assert len(body["suggestions"]) == 6


class TestHeadsUp:
    async def test_orders_overdue_ready_then_due_soon(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await task(api_client, auth_headers, "Soon", due_date="2026-11-24")
        ready = await task(api_client, auth_headers, "Ready")
        await api_client.patch(
            f"/tasks/{ready['id']}/steps/{ready['steps'][0]['id']}",
            json={"done": True},
            headers=auth_headers,
        )
        await task(api_client, auth_headers, "Late", due_date="2026-11-19")

        body = await plan(api_client, auth_headers)

        assert kinds(body["heads_up"]) == [
            ("overdue", "Late"),
            ("ready", "Ready"),
            ("due_soon", "Soon"),
        ]

    async def test_leaves_out_far_off_and_planned_tasks(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await task(api_client, auth_headers, "Far off", due_date="2026-12-20")
        planned = await task(api_client, auth_headers, "Planned", due_date=TODAY)
        await set_plan(api_client, auth_headers, TODAY, [planned["id"]])

        body = await plan(api_client, auth_headers)

        assert body["heads_up"] == []

    async def test_at_most_five(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        for n in range(7):
            await task(api_client, auth_headers, f"T{n}", due_date="2026-11-20")

        body = await plan(api_client, auth_headers)

        assert len(body["heads_up"]) == 5

    async def test_only_for_today(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await task(api_client, auth_headers, "Late", due_date="2026-11-20")

        body = await plan(api_client, auth_headers, "2026-11-23")

        assert body["heads_up"] == []

    async def test_never_shows_other_users_tasks(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        await task(api_client, other_headers, "Theirs", due_date="2026-11-20")

        body = await plan(api_client, auth_headers)

        assert (body["heads_up"], body["suggestions"]) == ([], [])
