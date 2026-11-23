"""API tests for creating notifications. "Now" is pinned to 2026-11-22 12:00 UTC."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import Goal

pytestmark = [pytest.mark.anyio, pytest.mark.db]

Headers = dict[str, str]
LONG_AGO = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


async def check(client: AsyncClient, headers: Headers) -> Any:
    return (await client.post("/notifications/check", headers=headers)).json()


async def listed(client: AsyncClient, headers: Headers) -> list[dict[str, Any]]:
    return (await client.get("/notifications", headers=headers)).json()


async def kinds(client: AsyncClient, headers: Headers) -> list[str]:
    return sorted(n["kind"] for n in await listed(client, headers))


async def new_goal(
    client: AsyncClient, headers: Headers, title: str = "Ship", **fields: Any
) -> dict[str, Any]:
    response = await client.post(
        "/goals", json={"title": title, **fields}, headers=headers
    )
    return response.json()


async def new_task(
    client: AsyncClient, headers: Headers, **fields: Any
) -> dict[str, Any]:
    response = await client.post(
        "/tasks", json={"title": "Task", "steps": ["Start"], **fields}, headers=headers
    )
    return response.json()


async def finish(client: AsyncClient, headers: Headers, task: dict[str, Any]) -> None:
    await client.patch(f"/tasks/{task['id']}", json={"status": "done"}, headers=headers)


class TestCheck:
    async def test_returns_the_unread_count(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await new_task(api_client, auth_headers, due_date="2026-11-23")

        assert await check(api_client, auth_headers) == {"unread": 1}

    async def test_checking_again_creates_nothing_new(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await new_goal(api_client, auth_headers, deadline="2026-11-25")
        await new_task(api_client, auth_headers, due_date="2026-11-23")
        await check(api_client, auth_headers)

        assert await check(api_client, auth_headers) == {"unread": 2}

    async def test_nothing_due_means_no_notifications(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        assert await check(api_client, auth_headers) == {"unread": 0}

    async def test_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/notifications/check")

        assert response.status_code == 401


class TestGoalDeadline:
    async def test_notifies_a_deadline_within_a_week(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await new_goal(api_client, auth_headers, deadline="2026-11-25")
        await check(api_client, auth_headers)

        [notification] = await listed(api_client, auth_headers)

        assert notification["title"] == "“Ship” is due in 3 days"
        assert notification["goal_id"] == goal["id"]

    @pytest.mark.parametrize(
        ("deadline", "when"), [("2026-11-22", "today"), ("2026-11-23", "tomorrow")]
    )
    async def test_says_today_or_tomorrow(
        self, api_client: AsyncClient, auth_headers: Headers, deadline: str, when: str
    ) -> None:
        await new_goal(api_client, auth_headers, deadline=deadline)
        await check(api_client, auth_headers)

        [notification] = await listed(api_client, auth_headers)

        assert notification["title"] == f"“Ship” is due {when}"

    @pytest.mark.parametrize("deadline", ["2026-11-30", "2026-11-21"])
    async def test_ignores_far_or_past_deadlines(
        self, api_client: AsyncClient, auth_headers: Headers, deadline: str
    ) -> None:
        await new_goal(api_client, auth_headers, deadline=deadline)

        await check(api_client, auth_headers)

        assert await listed(api_client, auth_headers) == []

    async def test_ignores_goals_that_are_not_active(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await new_goal(api_client, auth_headers, deadline="2026-11-25")
        await api_client.patch(
            f"/goals/{goal['id']}", json={"status": "completed"}, headers=auth_headers
        )

        await check(api_client, auth_headers)

        assert await listed(api_client, auth_headers) == []

    async def test_a_new_deadline_is_notified_again(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await new_goal(api_client, auth_headers, deadline="2026-11-25")
        await check(api_client, auth_headers)
        await api_client.patch(
            f"/goals/{goal['id']}",
            json={"deadline": "2026-11-27"},
            headers=auth_headers,
        )

        await check(api_client, auth_headers)

        assert len(await listed(api_client, auth_headers)) == 2


class TestGoalDone:
    async def test_notifies_when_every_task_is_done(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await new_goal(api_client, auth_headers)
        await finish(
            api_client,
            auth_headers,
            await new_task(api_client, auth_headers, goal_id=goal["id"]),
        )

        await check(api_client, auth_headers)

        [notification] = await listed(api_client, auth_headers)
        assert notification["title"] == "Every task for “Ship” is done"

    async def test_waits_while_any_task_is_open(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await new_goal(api_client, auth_headers)
        await finish(
            api_client,
            auth_headers,
            await new_task(api_client, auth_headers, goal_id=goal["id"]),
        )
        await new_task(api_client, auth_headers, goal_id=goal["id"])

        await check(api_client, auth_headers)

        assert await listed(api_client, auth_headers) == []

    async def test_ignores_goals_without_tasks(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await new_goal(api_client, auth_headers)

        await check(api_client, auth_headers)

        assert await listed(api_client, auth_headers) == []


class TestGoalStale:
    async def age(self, session: AsyncSession, goal_id: str) -> None:
        """Make the goal look untouched since long ago."""
        await session.execute(
            update(Goal)
            .where(Goal.id == uuid.UUID(goal_id))
            .values(updated_at=LONG_AGO)
        )

    async def test_notifies_a_goal_quiet_for_30_days(
        self, api_client: AsyncClient, auth_headers: Headers, db_session: AsyncSession
    ) -> None:
        goal = await new_goal(api_client, auth_headers)
        await self.age(db_session, goal["id"])

        await check(api_client, auth_headers)

        [notification] = await listed(api_client, auth_headers)
        assert notification["title"] == "“Ship” hasn't moved in 52 days"

    async def test_recent_task_activity_counts_as_movement(
        self, api_client: AsyncClient, auth_headers: Headers, db_session: AsyncSession
    ) -> None:
        goal = await new_goal(api_client, auth_headers)
        await new_task(api_client, auth_headers, goal_id=goal["id"])
        await self.age(db_session, goal["id"])

        await check(api_client, auth_headers)

        assert await listed(api_client, auth_headers) == []


class TestTasksDueSoon:
    async def test_one_summary_for_tasks_due_in_the_next_3_days(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        for due in ("2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25"):
            await new_task(api_client, auth_headers, due_date=due)

        await check(api_client, auth_headers)

        [notification] = await listed(api_client, auth_headers)
        assert notification["title"] == "3 tasks are due in the next 3 days"

    async def test_singular_wording_for_one_task(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await new_task(api_client, auth_headers, due_date="2026-11-23")

        await check(api_client, auth_headers)

        [notification] = await listed(api_client, auth_headers)
        assert notification["title"] == "1 task is due in the next 3 days"

    async def test_ignores_finished_and_overdue_tasks(
        self, api_client: AsyncClient, auth_headers: Headers, db_session: AsyncSession
    ) -> None:
        await finish(
            api_client,
            auth_headers,
            await new_task(api_client, auth_headers, due_date="2026-11-23"),
        )

        await check(api_client, auth_headers)

        assert await kinds(api_client, auth_headers) == []

    async def test_only_once_a_day(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await new_task(api_client, auth_headers, due_date="2026-11-23")
        await check(api_client, auth_headers)
        await new_task(api_client, auth_headers, due_date="2026-11-24")

        await check(api_client, auth_headers)

        assert await kinds(api_client, auth_headers) == ["tasks_due_soon"]

    async def test_keeps_users_apart(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        await new_task(api_client, other_headers, due_date="2026-11-23")

        await check(api_client, auth_headers)

        assert await listed(api_client, auth_headers) == []
