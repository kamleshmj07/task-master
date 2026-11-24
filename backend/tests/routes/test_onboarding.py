"""API tests for first-run setup ("Light the lamp")."""

from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.anyio, pytest.mark.db]

Headers = dict[str, str]
TODAY = "2026-11-22"


async def onboarding(client: AsyncClient, headers: Headers) -> Any:
    """The setup state as JSON."""
    response = await client.get("/onboarding", headers=headers)
    assert response.status_code == 200
    return response.json()


async def new_task(client: AsyncClient, headers: Headers) -> dict[str, Any]:
    """Create a task with two steps."""
    response = await client.post(
        "/tasks",
        json={"title": "Buy running shoes", "steps": ["Look up shops", "Try on"]},
        headers=headers,
    )
    return response.json()


class TestSteps:
    async def test_a_new_account_starts_with_nothing_lit(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        body = await onboarding(api_client, auth_headers)

        assert body == {
            "goal": None,
            "task": None,
            "three": False,
            "routine": None,
            "finished": False,
        }

    async def test_the_default_goal_does_not_count(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        goals = await api_client.get("/goals", headers=auth_headers)

        body = await onboarding(api_client, auth_headers)

        assert ([g["title"] for g in goals.json()], body["goal"]) == (
            ["Essentials"],
            None,
        )

    async def test_a_goal_of_their_own_lights_step_one(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await api_client.post(
            "/goals", json={"title": "Run a 10k"}, headers=auth_headers
        )

        body = await onboarding(api_client, auth_headers)

        assert body["goal"]["title"] == "Run a 10k"

    async def test_a_task_lights_step_two_with_its_first_step(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await new_task(api_client, auth_headers)

        body = await onboarding(api_client, auth_headers)

        assert (body["task"]["title"], body["task"]["first_step"]) == (
            "Buy running shoes",
            "Look up shops",
        )

    async def test_picking_a_three_lights_step_three(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)
        await api_client.put(
            f"/plans/{TODAY}", json={"task_ids": [task["id"]]}, headers=auth_headers
        )

        body = await onboarding(api_client, auth_headers)

        assert body["three"] is True

    async def test_a_routine_lights_step_four(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await api_client.post(
            "/routines",
            json={
                "title": "Take a walk",
                "frequency": "daily",
                "start_date": TODAY,
                "end_date": "2027-11-22",
            },
            headers=auth_headers,
        )

        body = await onboarding(api_client, auth_headers)

        assert body["routine"]["title"] == "Take a walk"

    async def test_never_counts_other_users_data(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        await new_task(api_client, other_headers)

        body = await onboarding(api_client, auth_headers)

        assert body["task"] is None


class TestFinish:
    async def test_finishing_is_remembered(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await api_client.post("/onboarding/finish", headers=auth_headers)

        body = await onboarding(api_client, auth_headers)

        assert body["finished"] is True

    async def test_finishing_twice_is_harmless(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await api_client.post("/onboarding/finish", headers=auth_headers)

        response = await api_client.post("/onboarding/finish", headers=auth_headers)

        assert (response.status_code, response.json()["finished"]) == (200, True)

    async def test_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/onboarding")

        assert response.status_code == 401
