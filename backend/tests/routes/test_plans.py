"""API tests for the daily Top 3 plan. "Today" is pinned to 2026-11-22."""

from typing import Any

import pytest
from httpx import AsyncClient

from tests.routes.test_routines import create_routine
from tests.routes.test_tasks import create_task

pytestmark = [pytest.mark.anyio, pytest.mark.db]

Headers = dict[str, str]
TODAY = "2026-11-22"


async def new_task(
    client: AsyncClient, headers: Headers, title: str, minutes: int = 60
) -> dict[str, Any]:
    """Create a goal-less task with an estimate."""
    response = await client.post(
        "/tasks",
        json={"title": title, "next_action": "Start", "estimate_minutes": minutes},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def set_plan(
    client: AsyncClient, headers: Headers, task_ids: list[str], day: str = TODAY
) -> Any:
    return await client.put(
        f"/plans/{day}", json={"task_ids": task_ids}, headers=headers
    )


class TestGetPlan:
    async def test_empty_day(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        response = await api_client.get(f"/plans/{TODAY}", headers=auth_headers)

        plan = response.json()
        assert (plan["top_three"], plan["routines"]) == ([], [])

    async def test_keeps_routines_separate_from_top_three(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, "Draft proposal")
        await create_routine(api_client, auth_headers, title="Workout")
        await set_plan(api_client, auth_headers, [task["id"]])

        plan = (await api_client.get(f"/plans/{TODAY}", headers=auth_headers)).json()

        assert [item["task"]["title"] for item in plan["top_three"]] == [
            "Draft proposal"
        ]
        assert [due["routine"]["title"] for due in plan["routines"]] == ["Workout"]

    async def test_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.get(f"/plans/{TODAY}")

        assert response.status_code == 401


class TestSetPlan:
    async def test_ranks_in_request_order(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        tasks = [await new_task(api_client, auth_headers, t) for t in "ABC"]

        response = await set_plan(
            api_client, auth_headers, [tasks[2]["id"], tasks[0]["id"], tasks[1]["id"]]
        )

        assert [
            (item["rank"], item["task"]["title"])
            for item in response.json()["top_three"]
        ] == [(1, "C"), (2, "A"), (3, "B")]

    async def test_replaces_the_previous_plan(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        first = await new_task(api_client, auth_headers, "First")
        second = await new_task(api_client, auth_headers, "Second")
        await set_plan(api_client, auth_headers, [first["id"]])

        response = await set_plan(api_client, auth_headers, [second["id"]])

        assert [i["task"]["title"] for i in response.json()["top_three"]] == ["Second"]

    async def test_can_clear_the_plan(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, "Only")
        await set_plan(api_client, auth_headers, [task["id"]])

        response = await set_plan(api_client, auth_headers, [])

        assert response.json()["top_three"] == []

    async def test_rejects_more_than_three(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        tasks = [await new_task(api_client, auth_headers, t) for t in "ABCD"]

        response = await set_plan(api_client, auth_headers, [t["id"] for t in tasks])

        assert response.status_code == 422

    async def test_rejects_duplicates(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, "Twice")

        response = await set_plan(api_client, auth_headers, [task["id"], task["id"]])

        assert response.status_code == 422

    async def test_rejects_past_days(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, "Late")

        response = await set_plan(
            api_client, auth_headers, [task["id"]], day="2026-11-21"
        )

        assert response.status_code == 422

    async def test_plans_future_days(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, "Tomorrow")

        response = await set_plan(
            api_client, auth_headers, [task["id"]], day="2026-11-23"
        )

        assert response.json()["plan_date"] == "2026-11-23"

    async def test_rejects_finished_task(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, "Done already")
        await api_client.patch(
            f"/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers
        )

        response = await set_plan(api_client, auth_headers, [task["id"]])

        assert response.status_code == 422

    async def test_task_finished_in_plan_may_stay(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        done = await new_task(api_client, auth_headers, "Done")
        other = await new_task(api_client, auth_headers, "Other")
        await set_plan(api_client, auth_headers, [done["id"]])
        await api_client.patch(
            f"/tasks/{done['id']}", json={"status": "done"}, headers=auth_headers
        )

        response = await set_plan(api_client, auth_headers, [other["id"], done["id"]])

        assert response.status_code == 200

    async def test_rejects_other_users_task(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        theirs = await new_task(api_client, other_headers, "Theirs")

        response = await set_plan(api_client, auth_headers, [theirs["id"]])

        assert response.status_code == 404

    async def test_plans_tasks_with_goals_too(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await api_client.post(
            "/goals", json={"title": "Ship"}, headers=auth_headers
        )
        task = await create_task(api_client, auth_headers, goal.json()["id"])

        response = await set_plan(api_client, auth_headers, [task["id"]])

        assert response.json()["top_three"][0]["task"]["goal_id"] == goal.json()["id"]


class TestCapacity:
    async def test_adds_top_three_and_routines(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, "Deep work", minutes=120)
        await create_routine(api_client, auth_headers, estimate_minutes=30)

        response = await set_plan(api_client, auth_headers, [task["id"]])

        assert response.json()["capacity"] == {
            "limit_minutes": 480,
            "planned_minutes": 150,
            "over": False,
        }

    async def test_flags_an_overfull_day(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        tasks = [await new_task(api_client, auth_headers, t, minutes=200) for t in "AB"]
        await create_routine(api_client, auth_headers, estimate_minutes=90)

        response = await set_plan(api_client, auth_headers, [t["id"] for t in tasks])

        assert response.json()["capacity"]["over"] is True
