"""API tests for notifications: tips saved when a task is postponed."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.anyio, pytest.mark.db]

Headers = dict[str, str]


async def postpone_new_task(
    client: AsyncClient, headers: Headers, reason: str = "stuck", title: str = "Tax"
) -> dict[str, Any]:
    """Create a dated task and postpone it, which saves a tip."""
    task = await client.post(
        "/tasks",
        json={"title": title, "steps": ["Start"], "due_date": "2099-01-01"},
        headers=headers,
    )
    response = await client.post(
        f"/tasks/{task.json()['id']}/postpone",
        json={"to_date": "2099-01-05", "reason": reason},
        headers=headers,
    )
    return response.json()


async def notifications(client: AsyncClient, headers: Headers, **params: Any) -> Any:
    return (await client.get("/notifications", params=params, headers=headers)).json()


class TestNotifications:
    async def test_postponing_saves_the_tip(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await postpone_new_task(api_client, auth_headers, "dreading")

        [saved] = await notifications(api_client, auth_headers)

        assert (saved["task_title"], saved["headline"], saved["read"]) == (
            "Tax",
            "Lower the bar to starting",
            False,
        )

    async def test_lists_newest_first(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await postpone_new_task(api_client, auth_headers, title="First")
        await postpone_new_task(api_client, auth_headers, title="Second")

        listed = await notifications(api_client, auth_headers)

        assert [n["task_title"] for n in listed] == ["Second", "First"]

    async def test_counts_unread(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await postpone_new_task(api_client, auth_headers)
        await postpone_new_task(api_client, auth_headers)

        response = await api_client.get(
            "/notifications/unread-count", headers=auth_headers
        )

        assert response.json() == {"unread": 2}

    async def test_marks_one_as_read(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await postpone_new_task(api_client, auth_headers)
        [saved] = await notifications(api_client, auth_headers)

        response = await api_client.post(
            f"/notifications/{saved['id']}/read", headers=auth_headers
        )

        unread = await notifications(api_client, auth_headers, unread_only=True)
        assert (response.json()["read"], unread) == (True, [])

    async def test_marks_all_as_read(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await postpone_new_task(api_client, auth_headers)
        await postpone_new_task(api_client, auth_headers)

        await api_client.post("/notifications/read-all", headers=auth_headers)

        count = await api_client.get(
            "/notifications/unread-count", headers=auth_headers
        )
        assert count.json() == {"unread": 0}

    async def test_survives_deleting_the_task(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        result = await postpone_new_task(api_client, auth_headers)

        await api_client.delete(f"/tasks/{result['task']['id']}", headers=auth_headers)

        [saved] = await notifications(api_client, auth_headers)
        assert (saved["task_id"], saved["task_title"]) == (None, "Tax")

    async def test_hides_other_users_notifications(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        await postpone_new_task(api_client, other_headers)

        assert await notifications(api_client, auth_headers) == []

    async def test_cannot_mark_other_users_notification(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        await postpone_new_task(api_client, other_headers)
        [theirs] = await notifications(api_client, other_headers)

        response = await api_client.post(
            f"/notifications/{theirs['id']}/read", headers=auth_headers
        )

        assert response.status_code == 404

    async def test_returns_404_for_unknown_notification(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        response = await api_client.post(
            f"/notifications/{uuid.uuid4()}/read", headers=auth_headers
        )

        assert response.status_code == 404

    async def test_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/notifications")

        assert response.status_code == 401
