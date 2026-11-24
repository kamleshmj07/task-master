"""The guessing limit on password re-checks (credential changes, deletion)."""

from datetime import timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import User, utc_now
from tests.auth.test_routes import EMAIL, PASSWORD

pytestmark = [pytest.mark.anyio, pytest.mark.db]

WRONG = "not-the-password-at-all"


def bearer(token: str) -> dict[str, str]:
    """Authorization header for `token`."""
    return {"Authorization": f"Bearer {token}"}


async def session_token(client: AsyncClient) -> str:
    """Register the test account and return a mobile access token."""
    await client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    form = {"username": EMAIL, "password": PASSWORD}
    response = await client.post("/auth/mobile/login", data=form)
    return response.json()["access_token"]


async def change_email(
    client: AsyncClient, token: str, current: str, email: str = "new@example.com"
) -> Response:
    """Try to change the email, giving `current` as the current password."""
    return await client.patch(
        "/users/me",
        json={"email": email, "current_password": current},
        headers=bearer(token),
    )


async def delete_account(client: AsyncClient, token: str, password: str) -> Response:
    """Try to delete the account with `password`."""
    return await client.request(
        "DELETE", "/users/me", json={"password": password}, headers=bearer(token)
    )


class TestGuessingLimit:
    async def test_says_how_many_tries_are_left(self, api_client: AsyncClient) -> None:
        token = await session_token(api_client)
        for _ in range(3):
            await change_email(api_client, token, WRONG)

        response = await change_email(api_client, token, WRONG)

        assert "1 more try" in response.json()["detail"]["reason"]

    async def test_fifth_wrong_password_pauses_checks(
        self, api_client: AsyncClient
    ) -> None:
        token = await session_token(api_client)
        for _ in range(4):
            await change_email(api_client, token, WRONG)

        fifth = await change_email(api_client, token, WRONG)

        assert fifth.status_code == 429

    async def test_the_right_password_is_refused_while_paused(
        self, api_client: AsyncClient
    ) -> None:
        token = await session_token(api_client)
        for _ in range(5):
            await change_email(api_client, token, WRONG)

        response = await change_email(api_client, token, PASSWORD)

        me = await api_client.get("/users/me", headers=bearer(token))
        assert (response.status_code, me.json()["email"]) == (429, EMAIL)

    async def test_deleting_shares_the_count(self, api_client: AsyncClient) -> None:
        token = await session_token(api_client)
        for _ in range(4):
            await change_email(api_client, token, WRONG)

        response = await delete_account(api_client, token, WRONG)

        assert response.status_code == 429

    async def test_paused_deletion_keeps_the_account(
        self, api_client: AsyncClient
    ) -> None:
        token = await session_token(api_client)
        for _ in range(5):
            await delete_account(api_client, token, WRONG)

        response = await delete_account(api_client, token, PASSWORD)

        me = await api_client.get("/users/me", headers=bearer(token))
        assert (response.status_code, me.status_code) == (429, 200)

    async def test_a_right_password_resets_the_count(
        self, api_client: AsyncClient
    ) -> None:
        token = await session_token(api_client)
        for _ in range(4):
            await change_email(api_client, token, WRONG)
        await change_email(api_client, token, PASSWORD)

        responses = [
            await change_email(api_client, token, WRONG, "other@example.com")
            for _ in range(4)
        ]

        assert [r.status_code for r in responses] == [400, 400, 400, 400]

    async def test_the_pause_ends_after_24_hours(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        token = await session_token(api_client)
        for _ in range(5):
            await change_email(api_client, token, WRONG)
        await db_session.execute(
            update(User).values(
                password_check_locked_until=utc_now() - timedelta(seconds=1)
            )
        )

        response = await change_email(api_client, token, PASSWORD)

        assert response.status_code == 200

    async def test_says_when_to_retry(self, api_client: AsyncClient) -> None:
        token = await session_token(api_client)
        for _ in range(5):
            await change_email(api_client, token, WRONG)

        response = await change_email(api_client, token, PASSWORD)

        assert int(response.headers["retry-after"]) > 23 * 3600
