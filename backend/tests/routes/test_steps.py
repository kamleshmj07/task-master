"""API tests for task steps."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.anyio, pytest.mark.db]

Headers = dict[str, str]


async def new_task(
    client: AsyncClient, headers: Headers, steps: list[str] | None = None
) -> dict[str, Any]:
    """Create a goal-less task with the given steps."""
    response = await client.post(
        "/tasks",
        json={"title": "Renew insurance", "steps": steps or ["Find policy", "Call"]},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def step_url(task: dict[str, Any], index: int | None = None) -> str:
    base = f"/tasks/{task['id']}/steps"
    return base if index is None else f"{base}/{task['steps'][index]['id']}"


class TestTaskSteps:
    async def test_create_keeps_step_order(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, ["One", "Two", "Three"])

        assert [step["text"] for step in task["steps"]] == ["One", "Two", "Three"]

    async def test_next_step_is_the_first_unfinished_one(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await api_client.patch(
            step_url(task, 0), json={"done": True}, headers=auth_headers
        )

        assert response.json()["next_step"] == "Call"

    async def test_next_step_is_none_when_all_done(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, ["Only"])

        response = await api_client.patch(
            step_url(task, 0), json={"done": True}, headers=auth_headers
        )

        assert response.json()["next_step"] is None

    async def test_ticking_the_last_step_leaves_task_open(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, ["Only"])

        response = await api_client.patch(
            step_url(task, 0), json={"done": True}, headers=auth_headers
        )

        assert response.json()["status"] == "todo"


class TestAddStep:
    async def test_appends_to_the_end(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await api_client.post(
            step_url(task), json={"text": "Pay"}, headers=auth_headers
        )

        assert response.status_code == 201
        assert [s["text"] for s in response.json()["steps"]] == [
            "Find policy",
            "Call",
            "Pay",
        ]

    async def test_rejects_blank_text(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await api_client.post(
            step_url(task), json={"text": "  "}, headers=auth_headers
        )

        assert response.status_code == 422

    async def test_caps_the_number_of_steps(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, ["s"] * 50)

        response = await api_client.post(
            step_url(task), json={"text": "one too many"}, headers=auth_headers
        )

        assert response.status_code == 422

    async def test_cannot_add_to_other_users_task(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        task = await new_task(api_client, other_headers)

        response = await api_client.post(
            step_url(task), json={"text": "Mine"}, headers=auth_headers
        )

        assert response.status_code == 404


class TestUpdateStep:
    async def test_renames(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await api_client.patch(
            step_url(task, 1), json={"text": "Call the broker"}, headers=auth_headers
        )

        assert response.json()["steps"][1]["text"] == "Call the broker"

    async def test_unticks(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)
        await api_client.patch(
            step_url(task, 0), json={"done": True}, headers=auth_headers
        )

        response = await api_client.patch(
            step_url(task, 0), json={"done": False}, headers=auth_headers
        )

        assert response.json()["steps"][0]["done"] is False

    async def test_rejects_null_done(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await api_client.patch(
            step_url(task, 0), json={"done": None}, headers=auth_headers
        )

        assert response.status_code == 422

    async def test_returns_404_for_step_of_another_task(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)
        other = await new_task(api_client, auth_headers)

        response = await api_client.patch(
            f"/tasks/{task['id']}/steps/{other['steps'][0]['id']}",
            json={"done": True},
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_returns_404_for_unknown_step(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await api_client.patch(
            f"/tasks/{task['id']}/steps/{uuid.uuid4()}",
            json={"done": True},
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestDeleteStep:
    async def test_removes_the_step(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await api_client.delete(step_url(task, 0), headers=auth_headers)

        assert [s["text"] for s in response.json()["steps"]] == ["Call"]

    async def test_keeps_at_least_one_step(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, ["Only"])

        response = await api_client.delete(step_url(task, 0), headers=auth_headers)

        assert response.status_code == 422

    async def test_cannot_delete_from_other_users_task(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        task = await new_task(api_client, other_headers)

        response = await api_client.delete(step_url(task, 0), headers=auth_headers)

        assert response.status_code == 404
