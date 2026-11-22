"""API tests for routines. "Today" is pinned to Sunday 2026-11-22."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.anyio, pytest.mark.db]

Headers = dict[str, str]
TODAY = "2026-11-22"
YESTERDAY = "2026-11-21"
TOMORROW = "2026-11-23"


async def create_routine(
    client: AsyncClient, headers: Headers, **fields: Any
) -> dict[str, Any]:
    """Create a daily routine running all of 2026 unless overridden."""
    payload = {
        "title": "Workout",
        "frequency": "daily",
        "estimate_minutes": 30,
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        **fields,
    }
    response = await client.post("/routines", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def completion_url(routine: dict[str, Any], day: str) -> str:
    return f"/routines/{routine['id']}/completions/{day}"


class TestCreateRoutine:
    async def test_returns_201_with_schedule(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(
            api_client, auth_headers, frequency="weekly", weekdays=[4, 0]
        )

        assert (routine["frequency"], routine["weekdays"]) == ("weekly", [0, 4])

    async def test_accepts_monthly(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(
            api_client, auth_headers, frequency="monthly", day_of_month=31
        )

        assert routine["day_of_month"] == 31

    @pytest.mark.parametrize(
        "fields",
        [
            {"frequency": "weekly"},
            {"frequency": "monthly"},
            {"end_date": "2025-01-01"},
            {"title": " "},
            {"estimate_minutes": 0},
        ],
    )
    async def test_rejects_invalid_routine(
        self, api_client: AsyncClient, auth_headers: Headers, fields: dict[str, Any]
    ) -> None:
        payload = {
            "title": "Workout",
            "frequency": "daily",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            **fields,
        }

        response = await api_client.post(
            "/routines", json=payload, headers=auth_headers
        )

        assert response.status_code == 422

    async def test_rejects_other_users_goal(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        goal = await api_client.post(
            "/goals", json={"title": "Theirs"}, headers=other_headers
        )

        response = await api_client.post(
            "/routines",
            json={
                "title": "Workout",
                "frequency": "daily",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "goal_id": goal.json()["id"],
            },
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/routines", json={})

        assert response.status_code == 401


class TestListRoutines:
    async def test_lists_only_own_routines(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        mine = await create_routine(api_client, auth_headers)
        await create_routine(api_client, other_headers)

        response = await api_client.get("/routines", headers=auth_headers)

        assert [r["id"] for r in response.json()] == [mine["id"]]

    async def test_filters_to_routines_running_on_a_day(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await create_routine(api_client, auth_headers, title="Running")
        await create_routine(
            api_client,
            auth_headers,
            title="Ended",
            start_date="2025-01-01",
            end_date="2025-12-31",
        )

        response = await api_client.get(
            "/routines", params={"active_on": TODAY}, headers=auth_headers
        )

        assert [r["title"] for r in response.json()] == ["Running"]


class TestDueRoutines:
    async def test_lists_routines_due_today(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await create_routine(api_client, auth_headers, title="Daily")
        await create_routine(
            api_client, auth_headers, title="Weekdays", frequency="weekly", weekdays=[0]
        )

        response = await api_client.get("/routines/due", headers=auth_headers)

        assert [d["routine"]["title"] for d in response.json()] == ["Daily"]

    async def test_lists_routines_due_on_another_day(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        await create_routine(
            api_client, auth_headers, title="Mondays", frequency="weekly", weekdays=[0]
        )

        response = await api_client.get(
            "/routines/due", params={"on": TOMORROW}, headers=auth_headers
        )

        assert [d["routine"]["title"] for d in response.json()] == ["Mondays"]

    async def test_reports_done_and_streak(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, auth_headers)
        for day in (YESTERDAY, TODAY):
            await api_client.put(completion_url(routine, day), headers=auth_headers)

        response = await api_client.get("/routines/due", headers=auth_headers)

        due = response.json()[0]
        assert (due["done"], due["streak"]) == (True, 2)


class TestTicking:
    async def test_tick_marks_the_day_done(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, auth_headers)

        response = await api_client.put(
            completion_url(routine, TODAY), headers=auth_headers
        )

        due = (await api_client.get("/routines/due", headers=auth_headers)).json()
        assert (response.status_code, due[0]["done"]) == (204, True)

    async def test_ticking_twice_is_harmless(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, auth_headers)
        await api_client.put(completion_url(routine, TODAY), headers=auth_headers)

        response = await api_client.put(
            completion_url(routine, TODAY), headers=auth_headers
        )

        assert response.status_code == 204

    async def test_untick_reverts_the_day(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, auth_headers)
        await api_client.put(completion_url(routine, TODAY), headers=auth_headers)

        await api_client.delete(completion_url(routine, TODAY), headers=auth_headers)

        due = (await api_client.get("/routines/due", headers=auth_headers)).json()
        assert due[0]["done"] is False

    async def test_rejects_future_day(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, auth_headers)

        response = await api_client.put(
            completion_url(routine, TOMORROW), headers=auth_headers
        )

        assert response.status_code == 422

    async def test_rejects_day_it_is_not_due(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(
            api_client, auth_headers, frequency="weekly", weekdays=[0]
        )

        response = await api_client.put(
            completion_url(routine, TODAY), headers=auth_headers
        )

        assert response.status_code == 422

    async def test_cannot_tick_other_users_routine(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, other_headers)

        response = await api_client.put(
            completion_url(routine, TODAY), headers=auth_headers
        )

        assert response.status_code == 404


class TestUpdateRoutine:
    async def test_switching_to_weekly_needs_weekdays(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, auth_headers)

        response = await api_client.patch(
            f"/routines/{routine['id']}",
            json={"frequency": "weekly"},
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_switching_frequency_drops_unused_details(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(
            api_client, auth_headers, frequency="weekly", weekdays=[1]
        )

        response = await api_client.patch(
            f"/routines/{routine['id']}",
            json={"frequency": "monthly", "day_of_month": 5},
            headers=auth_headers,
        )

        updated = response.json()
        assert (updated["weekdays"], updated["day_of_month"]) == (None, 5)

    async def test_rejects_end_before_start(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, auth_headers)

        response = await api_client.patch(
            f"/routines/{routine['id']}",
            json={"end_date": "2025-06-01"},
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_rejects_null_end_date(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, auth_headers)

        response = await api_client.patch(
            f"/routines/{routine['id']}",
            json={"end_date": None},
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_renames(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, auth_headers)

        response = await api_client.patch(
            f"/routines/{routine['id']}", json={"title": "Run"}, headers=auth_headers
        )

        assert response.json()["title"] == "Run"


class TestGetAndDelete:
    async def test_gets_own_routine(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, auth_headers)

        response = await api_client.get(
            f"/routines/{routine['id']}", headers=auth_headers
        )

        assert response.json() == routine

    async def test_hides_other_users_routine(
        self, api_client: AsyncClient, auth_headers: Headers, other_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, other_headers)

        response = await api_client.get(
            f"/routines/{routine['id']}", headers=auth_headers
        )

        assert response.status_code == 404

    async def test_deletes_routine(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        routine = await create_routine(api_client, auth_headers)

        await api_client.delete(f"/routines/{routine['id']}", headers=auth_headers)

        gone = await api_client.get(f"/routines/{routine['id']}", headers=auth_headers)
        assert gone.status_code == 404

    async def test_returns_404_for_unknown_routine(
        self, api_client: AsyncClient, auth_headers: Headers
    ) -> None:
        response = await api_client.delete(
            f"/routines/{uuid.uuid4()}", headers=auth_headers
        )

        assert response.status_code == 404
