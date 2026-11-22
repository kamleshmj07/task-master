"""API tests for task endpoints."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from tests.routes.test_goals import create_goal

pytestmark = [pytest.mark.anyio, pytest.mark.db]

Headers = dict[str, str]


async def create_task(
    client: AsyncClient, headers: Headers, goal_id: str, **fields: Any
) -> dict[str, Any]:
    """Create a task under `goal_id` and return its JSON body."""
    payload = {
        "goal_id": goal_id,
        "title": "Buy running shoes",
        "steps": ["Open the shop website", "Pick a pair"],
        "time_limit_minutes": 20,
        **fields,
    }
    response = await client.post("/tasks", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def goal_id_for(client: AsyncClient, headers: Headers) -> str:
    """Create a goal and return its id."""
    return (await create_goal(client, headers))["id"]


class TestCreateTask:
    async def test_starts_as_todo(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)

        task = await create_task(api_client, auth_headers, goal_id)

        assert (task["status"], task["postpone_count"], task["completed_at"]) == (
            "todo",
            0,
            None,
        )

    async def test_response_shape(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)

        task = await create_task(api_client, auth_headers, goal_id)

        assert set(task) == {
            "id",
            "goal_id",
            "title",
            "steps",
            "next_step",
            "time_limit_minutes",
            "due_date",
            "status",
            "postpone_count",
            "completed_at",
            "created_at",
            "updated_at",
        }

    @pytest.mark.parametrize(
        "fields",
        [
            {"steps": []},
            {"steps": ["   "]},
            {"steps": ["x" * 501]},
            {"steps": ["s"] * 51},
            {"time_limit_minutes": 0},
            {"time_limit_minutes": 1441},
            {"title": ""},
        ],
    )
    async def test_rejects_invalid_fields(
        self, api_client: AsyncClient, auth_headers: Headers, fields: dict[str, Any]
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)
        payload = {"goal_id": goal_id, "title": "T", "steps": ["Do it"], **fields}

        response = await api_client.post("/tasks", json=payload, headers=auth_headers)

        assert response.status_code == 422

    async def test_requires_steps(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)

        response = await api_client.post(
            "/tasks", json={"goal_id": goal_id, "title": "T"}, headers=auth_headers
        )

        assert response.status_code == 422

    async def test_rejects_other_users_goal(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        foreign_goal = await goal_id_for(api_client, other_headers)
        payload = {"goal_id": foreign_goal, "title": "T", "steps": ["Do it"]}

        response = await api_client.post("/tasks", json=payload, headers=auth_headers)

        assert response.status_code == 404

    async def test_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/tasks", json={})

        assert response.status_code == 401


class TestListTasks:
    async def test_lists_only_own_tasks(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        mine = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )
        await create_task(
            api_client, other_headers, await goal_id_for(api_client, other_headers)
        )

        response = await api_client.get("/tasks", headers=auth_headers)

        assert [task["id"] for task in response.json()] == [mine["id"]]

    async def test_orders_by_due_date_undated_last(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)
        await create_task(api_client, auth_headers, goal_id, title="Undated")
        await create_task(
            api_client, auth_headers, goal_id, title="Later", due_date="2026-12-10"
        )
        await create_task(
            api_client, auth_headers, goal_id, title="Sooner", due_date="2026-12-01"
        )

        response = await api_client.get("/tasks", headers=auth_headers)

        assert [task["title"] for task in response.json()] == [
            "Sooner",
            "Later",
            "Undated",
        ]

    async def test_filters_by_goal(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        first = await goal_id_for(api_client, auth_headers)
        second = await goal_id_for(api_client, auth_headers)
        await create_task(api_client, auth_headers, first, title="First")
        await create_task(api_client, auth_headers, second, title="Second")

        response = await api_client.get(
            "/tasks", params={"goal_id": second}, headers=auth_headers
        )

        assert [task["title"] for task in response.json()] == ["Second"]

    async def test_filters_by_status(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)
        done = await create_task(api_client, auth_headers, goal_id, title="Done")
        await create_task(api_client, auth_headers, goal_id, title="Open")
        await api_client.patch(
            f"/tasks/{done['id']}", json={"status": "done"}, headers=auth_headers
        )

        response = await api_client.get(
            "/tasks", params={"status": "todo"}, headers=auth_headers
        )

        assert [task["title"] for task in response.json()] == ["Open"]


class TestGetTask:
    async def test_returns_own_task(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )

        response = await api_client.get(f"/tasks/{task['id']}", headers=auth_headers)

        assert response.json() == task

    async def test_hides_other_users_task(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, other_headers, await goal_id_for(api_client, other_headers)
        )

        response = await api_client.get(f"/tasks/{task['id']}", headers=auth_headers)

        assert response.status_code == 404

    async def test_returns_404_for_unknown_id(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        response = await api_client.get(f"/tasks/{uuid.uuid4()}", headers=auth_headers)

        assert response.status_code == 404


class TestUpdateTask:
    async def test_marking_done_stamps_completion(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers
        )

        assert response.json()["completed_at"] is not None

    async def test_reopening_clears_completion(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )
        url = f"/tasks/{task['id']}"
        await api_client.patch(url, json={"status": "done"}, headers=auth_headers)

        response = await api_client.patch(
            url, json={"status": "todo"}, headers=auth_headers
        )

        assert response.json()["completed_at"] is None

    async def test_keeps_completion_when_already_done(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )
        url = f"/tasks/{task['id']}"
        first = await api_client.patch(
            url, json={"status": "done"}, headers=auth_headers
        )

        second = await api_client.patch(
            url, json={"status": "done"}, headers=auth_headers
        )

        assert second.json()["completed_at"] == first.json()["completed_at"]

    async def test_moves_task_to_another_own_goal(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )
        target = await goal_id_for(api_client, auth_headers)

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"goal_id": target}, headers=auth_headers
        )

        assert response.json()["goal_id"] == target

    async def test_cannot_move_task_to_other_users_goal(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )
        foreign_goal = await goal_id_for(api_client, other_headers)

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"goal_id": foreign_goal}, headers=auth_headers
        )

        assert response.status_code == 404

    async def test_rejects_null_title(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"title": None}, headers=auth_headers
        )

        assert response.status_code == 422

    async def test_clears_time_limit(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )

        response = await api_client.patch(
            f"/tasks/{task['id']}",
            json={"time_limit_minutes": None},
            headers=auth_headers,
        )

        assert response.json()["time_limit_minutes"] is None

    async def test_ignores_postpone_count(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"postpone_count": 9}, headers=auth_headers
        )

        assert response.json()["postpone_count"] == 0

    async def test_cannot_update_other_users_task(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, other_headers, await goal_id_for(api_client, other_headers)
        )

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"title": "Mine"}, headers=auth_headers
        )

        assert response.status_code == 404


class TestDueDateEdits:
    async def test_schedules_an_undated_task(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )

        response = await api_client.patch(
            f"/tasks/{task['id']}",
            json={"due_date": "2099-01-10"},
            headers=auth_headers,
        )

        assert response.json()["due_date"] == "2099-01-10"

    async def test_brings_a_date_forward(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client,
            auth_headers,
            await goal_id_for(api_client, auth_headers),
            due_date="2099-01-10",
        )

        response = await api_client.patch(
            f"/tasks/{task['id']}",
            json={"due_date": "2099-01-05"},
            headers=auth_headers,
        )

        assert response.json()["due_date"] == "2099-01-05"

    async def test_keeps_the_same_date(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client,
            auth_headers,
            await goal_id_for(api_client, auth_headers),
            due_date="2099-01-10",
        )

        response = await api_client.patch(
            f"/tasks/{task['id']}",
            json={"due_date": "2099-01-10"},
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.parametrize("due_date", ["2099-01-11", None])
    async def test_refuses_to_push_back_or_clear_a_date(
        self, api_client: AsyncClient, auth_headers: Headers, due_date: str | None
    ) -> None:
        task = await create_task(
            api_client,
            auth_headers,
            await goal_id_for(api_client, auth_headers),
            due_date="2099-01-10",
        )

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"due_date": due_date}, headers=auth_headers
        )

        assert response.status_code == 409

    async def test_refused_edit_changes_nothing(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client,
            auth_headers,
            await goal_id_for(api_client, auth_headers),
            due_date="2099-01-10",
        )
        url = f"/tasks/{task['id']}"
        await api_client.patch(
            url,
            json={"due_date": "2099-02-01", "title": "Sneaky"},
            headers=auth_headers,
        )

        stored = (await api_client.get(url, headers=auth_headers)).json()

        assert (stored["due_date"], stored["title"], stored["postpone_count"]) == (
            "2099-01-10",
            task["title"],
            0,
        )


class TestDeleteTask:
    async def test_deletes_task(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )

        response = await api_client.delete(f"/tasks/{task['id']}", headers=auth_headers)

        gone = await api_client.get(f"/tasks/{task['id']}", headers=auth_headers)
        assert (response.status_code, gone.status_code) == (204, 404)

    async def test_deleting_goal_deletes_its_tasks(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)
        task = await create_task(api_client, auth_headers, goal_id)

        await api_client.delete(f"/goals/{goal_id}", headers=auth_headers)

        gone = await api_client.get(f"/tasks/{task['id']}", headers=auth_headers)
        assert gone.status_code == 404

    async def test_cannot_delete_other_users_task(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, other_headers, await goal_id_for(api_client, other_headers)
        )

        response = await api_client.delete(f"/tasks/{task['id']}", headers=auth_headers)

        assert response.status_code == 404


class TestGoalLessTasks:
    async def test_creates_task_without_goal(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        response = await api_client.post(
            "/tasks",
            json={"title": "Renew insurance", "steps": ["Call the broker"]},
            headers=auth_headers,
        )

        assert (response.status_code, response.json()["goal_id"]) == (201, None)

    async def test_detaches_task_from_its_goal(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"goal_id": None}, headers=auth_headers
        )

        assert response.json()["goal_id"] is None

    async def test_filters_someday_tasks(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)
        await create_task(api_client, auth_headers, goal_id, title="Undated")
        await create_task(
            api_client, auth_headers, goal_id, title="Dated", due_date="2099-01-01"
        )

        someday = await api_client.get(
            "/tasks", params={"someday": True}, headers=auth_headers
        )
        dated = await api_client.get(
            "/tasks", params={"someday": False}, headers=auth_headers
        )

        assert (
            [t["title"] for t in someday.json()],
            [t["title"] for t in dated.json()],
        ) == (["Undated"], ["Dated"])


class TestCountsAndPaging:
    async def test_counts_each_view(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)
        await create_task(api_client, auth_headers, goal_id, due_date="2099-01-01")
        await create_task(api_client, auth_headers, goal_id)
        done = await create_task(api_client, auth_headers, goal_id)
        await api_client.patch(
            f"/tasks/{done['id']}", json={"status": "done"}, headers=auth_headers
        )

        response = await api_client.get("/tasks/counts", headers=auth_headers)

        assert response.json() == {
            "scheduled": 1,
            "review": 0,
            "someday": 1,
            "done": 1,
        }

    async def test_counts_only_own_tasks(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        await create_task(
            api_client, other_headers, await goal_id_for(api_client, other_headers)
        )

        response = await api_client.get("/tasks/counts", headers=auth_headers)

        assert response.json() == {
            "scheduled": 0,
            "review": 0,
            "someday": 0,
            "done": 0,
        }

    async def test_counts_follow_the_goal_filters(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)
        await create_task(api_client, auth_headers, goal_id)
        await api_client.post(
            "/tasks", json={"title": "Loose", "steps": ["Go"]}, headers=auth_headers
        )

        by_goal = await api_client.get(
            "/tasks/counts", params={"goal_id": goal_id}, headers=auth_headers
        )
        no_goal = await api_client.get(
            "/tasks/counts", params={"no_goal": True}, headers=auth_headers
        )

        assert (by_goal.json()["someday"], no_goal.json()["someday"]) == (1, 1)

    async def test_lists_only_goal_less_tasks(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await create_task(
            api_client, auth_headers, await goal_id_for(api_client, auth_headers)
        )
        await api_client.post(
            "/tasks", json={"title": "Loose", "steps": ["Go"]}, headers=auth_headers
        )

        response = await api_client.get(
            "/tasks", params={"no_goal": True}, headers=auth_headers
        )

        assert [task["title"] for task in response.json()] == ["Loose"]

    async def test_lists_finished_tasks_most_recent_first(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)
        for title in ("First done", "Second done"):
            task = await create_task(api_client, auth_headers, goal_id, title=title)
            await api_client.patch(
                f"/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers
            )

        response = await api_client.get(
            "/tasks", params={"status": "done"}, headers=auth_headers
        )

        assert [t["title"] for t in response.json()] == ["Second done", "First done"]

    async def test_pages_fifty_at_a_time_by_default(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await goal_id_for(api_client, auth_headers)
        for index in range(51):
            await create_task(api_client, auth_headers, goal_id, title=f"T{index}")

        first = await api_client.get("/tasks", headers=auth_headers)
        rest = await api_client.get(
            "/tasks", params={"offset": 50}, headers=auth_headers
        )

        assert (len(first.json()), len(rest.json())) == (50, 1)


class TestReviewView:
    """Pinned today is 2026-11-22."""

    async def create(
        self, client: AsyncClient, headers: Headers, title: str, **fields: Any
    ) -> dict[str, Any]:
        response = await client.post(
            "/tasks",
            json={"title": title, "steps": ["Only"], **fields},
            headers=headers,
        )
        return response.json()

    async def titles(
        self, client: AsyncClient, headers: Headers, view: str
    ) -> list[str]:
        response = await client.get("/tasks", params={"view": view}, headers=headers)
        return [task["title"] for task in response.json()]

    async def test_overdue_tasks_move_to_review(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await self.create(api_client, auth_headers, "Late", due_date="2026-11-21")
        await self.create(api_client, auth_headers, "Today", due_date="2026-11-22")

        review = await self.titles(api_client, auth_headers, "review")
        scheduled = await self.titles(api_client, auth_headers, "scheduled")

        assert (review, scheduled) == (["Late"], ["Today"])

    async def test_tasks_with_every_step_done_move_to_review(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await self.create(api_client, auth_headers, "Ready")
        step_id = task["steps"][0]["id"]
        await api_client.patch(
            f"/tasks/{task['id']}/steps/{step_id}",
            json={"done": True},
            headers=auth_headers,
        )

        review = await self.titles(api_client, auth_headers, "review")
        someday = await self.titles(api_client, auth_headers, "someday")

        assert (review, someday) == (["Ready"], [])

    async def test_each_task_is_in_exactly_one_view(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await self.create(api_client, auth_headers, "Late", due_date="2026-11-01")
        await self.create(api_client, auth_headers, "Soon", due_date="2026-11-25")
        await self.create(api_client, auth_headers, "Undated")
        done = await self.create(api_client, auth_headers, "Finished")
        await api_client.patch(
            f"/tasks/{done['id']}", json={"status": "done"}, headers=auth_headers
        )

        response = await api_client.get("/tasks/counts", headers=auth_headers)

        assert response.json() == {
            "scheduled": 1,
            "review": 1,
            "someday": 1,
            "done": 1,
        }

    async def test_rejects_unknown_view(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        response = await api_client.get(
            "/tasks", params={"view": "later"}, headers=auth_headers
        )

        assert response.status_code == 422
