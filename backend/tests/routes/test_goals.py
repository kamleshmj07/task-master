"""API tests for goal endpoints."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from task_master.defaults import DEFAULT_GOAL_TITLE

pytestmark = [pytest.mark.anyio, pytest.mark.db]

Headers = dict[str, str]
GOAL = {"title": "Run a marathon", "why": "Prove I can", "deadline": "2027-04-01"}


async def create_goal(
    client: AsyncClient, headers: Headers, **fields: Any
) -> dict[str, Any]:
    """Create a goal and return its JSON body."""
    response = await client.post("/goals", json={**GOAL, **fields}, headers=headers)
    assert response.status_code == 201
    return response.json()


async def default_goal_id(client: AsyncClient, headers: Headers) -> str:
    """Id of the goal every account starts with."""
    goals = (await client.get("/goals", headers=headers)).json()
    return next(g["id"] for g in goals if g["title"] == DEFAULT_GOAL_TITLE)


class TestDefaultGoal:
    async def test_new_account_starts_with_essentials(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        response = await api_client.get("/goals", headers=auth_headers)

        assert [goal["title"] for goal in response.json()] == [DEFAULT_GOAL_TITLE]

    async def test_default_goal_is_an_ordinary_goal(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal_id = await default_goal_id(api_client, auth_headers)

        response = await api_client.delete(f"/goals/{goal_id}", headers=auth_headers)

        assert response.status_code == 204


class TestCreateGoal:
    async def test_returns_201_with_goal(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)

        assert (goal["title"], goal["status"]) == ("Run a marathon", "active")

    async def test_response_shape(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)

        assert set(goal) == {
            "id",
            "title",
            "why",
            "deadline",
            "status",
            "created_at",
            "updated_at",
            "progress",
        }

    async def test_strips_title_whitespace(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers, title="  Learn Go  ")

        assert goal["title"] == "Learn Go"

    @pytest.mark.parametrize("title", ["", "   ", "x" * 201])
    async def test_rejects_invalid_title(
        self, api_client: AsyncClient, auth_headers: Headers, title: str
    ) -> None:
        response = await api_client.post(
            "/goals", json={"title": title}, headers=auth_headers
        )

        assert response.status_code == 422

    async def test_rejects_empty_payload(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        response = await api_client.post("/goals", json={}, headers=auth_headers)

        assert response.status_code == 422

    async def test_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/goals", json=GOAL)

        assert response.status_code == 401


class TestListGoals:
    async def test_lists_only_own_goals(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        mine = await create_goal(api_client, auth_headers)
        await create_goal(api_client, other_headers)

        response = await api_client.get("/goals", headers=auth_headers)

        ids = {goal["id"] for goal in response.json()}
        assert ids == {mine["id"], await default_goal_id(api_client, auth_headers)}

    async def test_filters_by_status(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        done = await create_goal(api_client, auth_headers, title="Done")
        await create_goal(api_client, auth_headers, title="Open")
        await api_client.patch(
            f"/goals/{done['id']}", json={"status": "completed"}, headers=auth_headers
        )

        response = await api_client.get(
            "/goals", params={"status": "completed"}, headers=auth_headers
        )

        assert [goal["title"] for goal in response.json()] == ["Done"]

    async def test_paginates_a_stable_order(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        for title in ("One", "Two", "Three"):
            await create_goal(api_client, auth_headers, title=title)
        everything = (await api_client.get("/goals", headers=auth_headers)).json()

        response = await api_client.get(
            "/goals", params={"limit": 1, "offset": 1}, headers=auth_headers
        )

        assert response.json() == everything[1:2]

    @pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
    async def test_rejects_bad_pagination(
        self, api_client: AsyncClient, auth_headers: Headers, params: dict[str, int]
    ) -> None:
        response = await api_client.get("/goals", params=params, headers=auth_headers)

        assert response.status_code == 422


class TestGetGoal:
    async def test_returns_own_goal(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)

        response = await api_client.get(f"/goals/{goal['id']}", headers=auth_headers)

        assert response.json() == goal

    async def test_hides_other_users_goal(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, other_headers)

        response = await api_client.get(f"/goals/{goal['id']}", headers=auth_headers)

        assert response.status_code == 404

    async def test_returns_404_for_unknown_id(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        response = await api_client.get(f"/goals/{uuid.uuid4()}", headers=auth_headers)

        assert response.status_code == 404

    async def test_rejects_malformed_id(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        response = await api_client.get("/goals/not-a-uuid", headers=auth_headers)

        assert response.status_code == 422


class TestUpdateGoal:
    async def test_changes_only_sent_fields(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)

        response = await api_client.patch(
            f"/goals/{goal['id']}", json={"title": "Run a half"}, headers=auth_headers
        )

        updated = response.json()
        assert (updated["title"], updated["why"]) == ("Run a half", goal["why"])

    async def test_clears_nullable_field(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)

        response = await api_client.patch(
            f"/goals/{goal['id']}", json={"deadline": None}, headers=auth_headers
        )

        assert response.json()["deadline"] is None

    async def test_rejects_null_title(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)

        response = await api_client.patch(
            f"/goals/{goal['id']}", json={"title": None}, headers=auth_headers
        )

        assert response.status_code == 422

    async def test_rejects_unknown_status(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)

        response = await api_client.patch(
            f"/goals/{goal['id']}", json={"status": "paused"}, headers=auth_headers
        )

        assert response.status_code == 422

    async def test_cannot_update_other_users_goal(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, other_headers)

        response = await api_client.patch(
            f"/goals/{goal['id']}", json={"title": "Mine now"}, headers=auth_headers
        )

        assert response.status_code == 404


class TestDeleteGoal:
    async def test_deletes_goal(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)

        response = await api_client.delete(f"/goals/{goal['id']}", headers=auth_headers)

        gone = await api_client.get(f"/goals/{goal['id']}", headers=auth_headers)
        assert (response.status_code, gone.status_code) == (204, 404)

    async def test_cannot_delete_other_users_goal(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, other_headers)

        response = await api_client.delete(f"/goals/{goal['id']}", headers=auth_headers)

        assert response.status_code == 404


async def add_task(
    client: AsyncClient, headers: Headers, goal_id: str, **fields: Any
) -> dict[str, Any]:
    response = await client.post(
        "/tasks",
        json={"title": "T", "steps": ["Go"], "goal_id": goal_id, **fields},
        headers=headers,
    )
    return response.json()


class TestGoalProgress:
    async def test_new_goal_has_nothing_yet(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)

        progress = goal["progress"]

        assert (
            progress["total_tasks"],
            progress["done_tasks"],
            progress["routine_count"],
            progress["next_due_task"],
        ) == (0, 0, 0, None)

    async def test_counts_tasks_and_finished_ones(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)
        done = await add_task(api_client, auth_headers, goal["id"])
        await add_task(api_client, auth_headers, goal["id"])
        await api_client.patch(
            f"/tasks/{done['id']}", json={"status": "done"}, headers=auth_headers
        )

        response = await api_client.get(f"/goals/{goal['id']}", headers=auth_headers)

        progress = response.json()["progress"]
        assert (progress["total_tasks"], progress["done_tasks"]) == (2, 1)

    async def test_names_the_soonest_open_task(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)
        await add_task(
            api_client, auth_headers, goal["id"], title="Later", due_date="2099-02-01"
        )
        await add_task(
            api_client, auth_headers, goal["id"], title="Sooner", due_date="2099-01-01"
        )
        await add_task(api_client, auth_headers, goal["id"], title="Undated")

        response = await api_client.get(f"/goals/{goal['id']}", headers=auth_headers)

        assert response.json()["progress"]["next_due_task"]["title"] == "Sooner"

    async def test_counts_routines(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)
        await api_client.post(
            "/routines",
            json={
                "title": "Run",
                "frequency": "daily",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "goal_id": goal["id"],
            },
            headers=auth_headers,
        )

        response = await api_client.get(f"/goals/{goal['id']}", headers=auth_headers)

        assert response.json()["progress"]["routine_count"] == 1

    async def test_lists_progress_for_every_goal(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        first = await create_goal(api_client, auth_headers, title="First")
        await create_goal(api_client, auth_headers, title="Second")
        await add_task(api_client, auth_headers, first["id"])

        response = await api_client.get("/goals", headers=auth_headers)

        totals = {g["title"]: g["progress"]["total_tasks"] for g in response.json()}
        assert (totals["First"], totals["Second"]) == (1, 0)

    async def test_editing_keeps_progress(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)
        await add_task(api_client, auth_headers, goal["id"])

        response = await api_client.patch(
            f"/goals/{goal['id']}",
            json={"title": "Run a half", "why": "Build up", "deadline": "2099-05-01"},
            headers=auth_headers,
        )

        updated = response.json()
        assert updated["title"] == "Run a half"
        assert updated["progress"]["total_tasks"] == 1

    async def test_deleting_a_goal_deletes_its_tasks(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goal = await create_goal(api_client, auth_headers)
        task = await add_task(api_client, auth_headers, goal["id"])

        await api_client.delete(f"/goals/{goal['id']}", headers=auth_headers)

        gone = await api_client.get(f"/tasks/{task['id']}", headers=auth_headers)
        assert gone.status_code == 404
