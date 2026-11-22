"""API tests for postponing tasks and reading postponement history."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response

from tests.routes.test_tasks import create_task, goal_id_for

pytestmark = [pytest.mark.anyio, pytest.mark.db]

Headers = dict[str, str]
# Far-future dates keep these tests independent of today's date.
DUE = "2099-01-10"
LATER = "2099-01-12"
LATEST = "2099-01-15"


async def new_task(
    client: AsyncClient, headers: Headers, **fields: Any
) -> dict[str, Any]:
    """Create a task due on `DUE` and return its JSON body."""
    goal_id = await goal_id_for(client, headers)
    return await create_task(client, headers, goal_id, **{"due_date": DUE, **fields})


async def postpone(
    client: AsyncClient,
    headers: Headers,
    task_id: str,
    reason: str = "stuck",
    to_date: str | None = LATER,
    **fields: Any,
) -> Response:
    """Postpone a task and return the raw response."""
    payload = {"to_date": to_date, "reason": reason, **fields}
    return await client.post(
        f"/tasks/{task_id}/postpone", json=payload, headers=headers
    )


class TestPostpone:
    async def test_moves_the_due_date(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await postpone(api_client, auth_headers, task["id"])

        assert response.status_code == 201
        assert response.json()["task"]["due_date"] == LATER

    async def test_counts_the_postponement(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)
        await postpone(api_client, auth_headers, task["id"])

        response = await postpone(api_client, auth_headers, task["id"], to_date=LATEST)

        assert response.json()["task"]["postpone_count"] == 2

    async def test_records_where_it_moved_from(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await postpone(api_client, auth_headers, task["id"])

        recorded = response.json()["postponement"]
        assert (recorded["from_date"], recorded["to_date"]) == (DUE, LATER)

    async def test_returns_the_fix_for_the_reason(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await postpone(api_client, auth_headers, task["id"], "dreading")

        assert response.json()["suggestion"]["headline"] == (
            "Lower the bar to starting"
        )

    async def test_third_blocked_postponement_asks_about_dread(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)
        for to_date in ("2099-01-11", "2099-01-12"):
            await postpone(api_client, auth_headers, task["id"], "blocked", to_date)

        response = await postpone(
            api_client, auth_headers, task["id"], "blocked", "2099-01-13"
        )

        assert response.json()["suggestion"]["reflection"] is not None

    async def test_undated_task_can_be_scheduled(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, due_date=None)

        response = await postpone(api_client, auth_headers, task["id"])

        assert response.json()["postponement"]["from_date"] is None

    async def test_stores_note_for_other(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await postpone(
            api_client, auth_headers, task["id"], "other", note="Sick day"
        )

        assert response.json()["postponement"]["note"] == "Sick day"

    async def test_rejects_other_without_note(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await postpone(api_client, auth_headers, task["id"], "other")

        assert response.status_code == 422

    async def test_rejects_unknown_reason(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await postpone(api_client, auth_headers, task["id"], "lazy")

        assert response.status_code == 422

    @pytest.mark.parametrize("to_date", [DUE, "2099-01-09"])
    async def test_rejects_date_not_after_due_date(
        self, api_client: AsyncClient, auth_headers: Headers, to_date: str
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await postpone(api_client, auth_headers, task["id"], to_date=to_date)

        assert response.status_code == 422

    async def test_rejects_date_in_the_past(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, due_date=None)

        response = await postpone(
            api_client, auth_headers, task["id"], to_date="2000-01-01"
        )

        assert response.status_code == 422

    async def test_rejected_postponement_changes_nothing(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)
        await postpone(api_client, auth_headers, task["id"], to_date=DUE)

        stored = await api_client.get(f"/tasks/{task['id']}", headers=auth_headers)

        assert (stored.json()["due_date"], stored.json()["postpone_count"]) == (
            DUE,
            0,
        )

    async def test_rejects_finished_task(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)
        await api_client.patch(
            f"/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers
        )

        response = await postpone(api_client, auth_headers, task["id"])

        assert response.status_code == 409

    async def test_cannot_postpone_other_users_task(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        task = await new_task(api_client, other_headers)

        response = await postpone(api_client, auth_headers, task["id"])

        assert response.status_code == 404

    async def test_returns_404_for_unknown_task(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        response = await postpone(api_client, auth_headers, str(uuid.uuid4()))

        assert response.status_code == 404

    async def test_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await postpone(api_client, {}, str(uuid.uuid4()))

        assert response.status_code == 401


class TestHistory:
    async def test_lists_postponements_oldest_first(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)
        await postpone(api_client, auth_headers, task["id"], "stuck", LATER)
        await postpone(api_client, auth_headers, task["id"], "dreading", LATEST)

        response = await api_client.get(
            f"/tasks/{task['id']}/postponements", headers=auth_headers
        )

        assert [row["reason"] for row in response.json()] == ["stuck", "dreading"]

    async def test_new_task_has_no_history(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await api_client.get(
            f"/tasks/{task['id']}/postponements", headers=auth_headers
        )

        assert response.json() == []

    async def test_hides_other_users_history(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        task = await new_task(api_client, other_headers)

        response = await api_client.get(
            f"/tasks/{task['id']}/postponements", headers=auth_headers
        )

        assert response.status_code == 404


class TestSomeday:
    async def test_moves_dated_task_to_someday(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await postpone(
            api_client, auth_headers, task["id"], "blocked", to_date=None
        )

        body = response.json()
        assert (body["task"]["due_date"], body["postponement"]["to_date"]) == (
            None,
            None,
        )

    async def test_counts_as_a_postponement(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await postpone(api_client, auth_headers, task["id"], to_date=None)

        assert response.json()["task"]["postpone_count"] == 1

    async def test_still_needs_a_reason(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)

        response = await api_client.post(
            f"/tasks/{task['id']}/postpone",
            json={"to_date": None},
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_rejects_task_already_in_someday(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers, due_date=None)

        response = await postpone(api_client, auth_headers, task["id"], to_date=None)

        assert response.status_code == 422

    async def test_someday_task_can_be_scheduled_again(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        task = await new_task(api_client, auth_headers)
        await postpone(api_client, auth_headers, task["id"], to_date=None)

        response = await api_client.patch(
            f"/tasks/{task['id']}", json={"due_date": LATEST}, headers=auth_headers
        )

        assert response.json()["due_date"] == LATEST
