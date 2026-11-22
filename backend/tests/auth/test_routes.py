"""API tests for registration, login, refresh, logout and the current user."""

from http.cookies import SimpleCookie

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.auth.routes import REFRESH_COOKIE
from task_master.models import (
    Goal,
    Notification,
    RefreshToken,
    Task,
    TaskStep,
    User,
)

pytestmark = [pytest.mark.anyio, pytest.mark.db]

EMAIL = "ada@example.com"
PASSWORD = "correct-horse-battery"


async def _register(client: AsyncClient, **fields: object) -> Response:
    payload = {"email": EMAIL, "password": PASSWORD, **fields}
    return await client.post("/auth/register", json=payload)


async def _login(client: AsyncClient, kind: str, password: str = PASSWORD) -> Response:
    form = {"username": EMAIL, "password": password}
    return await client.post(f"/auth/{kind}/login", data=form)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _refresh_cookie(response: Response) -> SimpleCookie:
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return cookie


async def _web_session(client: AsyncClient) -> tuple[str, str]:
    """Register and log in on the web; return access token and refresh cookie."""
    await _register(client)
    response = await _login(client, "web")
    return response.json()["access_token"], client.cookies[REFRESH_COOKIE]


async def _mobile_session(client: AsyncClient) -> tuple[str, str]:
    """Register and log in on mobile; return access and refresh tokens."""
    await _register(client)
    body = (await _login(client, "mobile")).json()
    return body["access_token"], body["refresh_token"]


async def _web_refresh_with(client: AsyncClient, token: str) -> Response:
    """Send exactly `token` as the refresh cookie, bypassing the cookie jar."""
    client.cookies.clear()
    headers = {"Cookie": f"{REFRESH_COOKIE}={token}"}
    return await client.post("/auth/web/refresh", headers=headers)


class TestRegister:
    async def test_returns_201_with_public_fields(
        self, api_client: AsyncClient
    ) -> None:
        response = await _register(api_client, timezone="Asia/Kolkata")

        assert response.status_code == 201
        assert set(response.json()) == {
            "id",
            "email",
            "is_active",
            "is_superuser",
            "is_verified",
            "timezone",
            "display_name",
        }

    async def test_ignores_superuser_flag(self, api_client: AsyncClient) -> None:
        response = await _register(api_client, is_superuser=True)

        assert response.json()["is_superuser"] is False

    async def test_rejects_short_password(self, api_client: AsyncClient) -> None:
        response = await _register(api_client, password="short")

        assert response.status_code == 400

    async def test_rejects_password_containing_email(
        self, api_client: AsyncClient
    ) -> None:
        response = await _register(api_client, password="ada-is-my-password")

        assert response.status_code == 400

    async def test_rejects_duplicate_email_in_any_case(
        self, api_client: AsyncClient
    ) -> None:
        await _register(api_client)

        response = await _register(api_client, email=EMAIL.upper())

        assert response.status_code == 400

    async def test_rejects_unknown_timezone(self, api_client: AsyncClient) -> None:
        response = await _register(api_client, timezone="Mars/Olympus")

        assert response.status_code == 422

    async def test_rejects_missing_password(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/auth/register", json={"email": EMAIL})

        assert response.status_code == 422


class TestWebLogin:
    async def test_returns_access_token_only(self, api_client: AsyncClient) -> None:
        await _register(api_client)

        response = await _login(api_client, "web")

        assert set(response.json()) == {"access_token", "token_type", "expires_in"}

    async def test_sets_locked_down_refresh_cookie(
        self, api_client: AsyncClient
    ) -> None:
        await _register(api_client)

        morsel = _refresh_cookie(await _login(api_client, "web"))[REFRESH_COOKIE]

        assert (
            morsel["httponly"],
            morsel["secure"],
            morsel["samesite"],
            morsel["path"],
        ) == (True, True, "strict", "/auth/web")

    async def test_rejects_wrong_password(self, api_client: AsyncClient) -> None:
        await _register(api_client)

        response = await _login(api_client, "web", password="wrong-password-123")

        assert response.status_code == 400

    async def test_rejects_unknown_email(self, api_client: AsyncClient) -> None:
        response = await _login(api_client, "web")

        assert response.status_code == 400

    async def test_locks_account_after_five_failures(
        self, api_client: AsyncClient
    ) -> None:
        await _register(api_client)
        for _ in range(5):
            await _login(api_client, "web", password="wrong-password-123")

        response = await _login(api_client, "web")

        assert (response.status_code, response.headers["retry-after"]) == (
            429,
            "60",
        )

    async def test_unknown_email_locks_the_same_way(
        self, api_client: AsyncClient
    ) -> None:
        for _ in range(5):
            await _login(api_client, "web")

        response = await _login(api_client, "web")

        assert (response.status_code, response.headers["retry-after"]) == (
            429,
            "60",
        )

    async def test_successful_logins_are_not_throttled(
        self, api_client: AsyncClient
    ) -> None:
        await _register(api_client)

        statuses = [(await _login(api_client, "web")).status_code for _ in range(8)]

        assert statuses == [200] * 8

    async def test_success_resets_the_failure_count(
        self, api_client: AsyncClient
    ) -> None:
        await _register(api_client)
        for _ in range(4):
            await _login(api_client, "web", password="wrong-password-123")
        await _login(api_client, "web")

        await _login(api_client, "web", password="wrong-password-123")
        response = await _login(api_client, "web")

        assert response.status_code == 200

    async def test_lockout_spans_web_and_mobile(self, api_client: AsyncClient) -> None:
        await _register(api_client)
        for _ in range(5):
            await _login(api_client, "web", password="wrong-password-123")

        response = await _login(api_client, "mobile")

        assert response.status_code == 429


class TestWebRefresh:
    async def test_issues_new_access_token_and_cookie(
        self, api_client: AsyncClient
    ) -> None:
        access_token, refresh_token = await _web_session(api_client)

        response = await _web_refresh_with(api_client, refresh_token)

        new_cookie = api_client.cookies[REFRESH_COOKIE]
        assert response.status_code == 200
        assert response.json()["access_token"] != access_token
        assert new_cookie != refresh_token

    async def test_rejects_missing_cookie(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/auth/web/refresh")

        assert response.status_code == 401

    async def test_rejects_reused_cookie(self, api_client: AsyncClient) -> None:
        _, refresh_token = await _web_session(api_client)
        await _web_refresh_with(api_client, refresh_token)

        response = await _web_refresh_with(api_client, refresh_token)

        assert response.status_code == 401


class TestWebLogout:
    async def test_revokes_access_token(self, api_client: AsyncClient) -> None:
        access_token, _ = await _web_session(api_client)

        await api_client.post("/auth/web/logout", headers=_bearer(access_token))

        me = await api_client.get("/users/me", headers=_bearer(access_token))
        assert me.status_code == 401

    async def test_revokes_refresh_cookie(self, api_client: AsyncClient) -> None:
        access_token, refresh_token = await _web_session(api_client)

        response = await api_client.post(
            "/auth/web/logout", headers=_bearer(access_token)
        )

        assert response.status_code == 204
        refreshed = await _web_refresh_with(api_client, refresh_token)
        assert refreshed.status_code == 401

    async def test_clears_refresh_cookie(self, api_client: AsyncClient) -> None:
        access_token, _ = await _web_session(api_client)

        await api_client.post("/auth/web/logout", headers=_bearer(access_token))

        assert REFRESH_COOKIE not in api_client.cookies

    async def test_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/auth/web/logout")

        assert response.status_code == 401


class TestMobile:
    async def test_login_returns_token_pair(self, api_client: AsyncClient) -> None:
        await _register(api_client)

        response = await _login(api_client, "mobile")

        assert set(response.json()) == {
            "access_token",
            "refresh_token",
            "token_type",
            "expires_in",
        }

    async def test_login_sets_no_cookie(self, api_client: AsyncClient) -> None:
        await _register(api_client)

        response = await _login(api_client, "mobile")

        assert "set-cookie" not in response.headers

    async def test_refresh_rotates_tokens(self, api_client: AsyncClient) -> None:
        _, refresh_token = await _mobile_session(api_client)

        response = await api_client.post(
            "/auth/mobile/refresh", json={"refresh_token": refresh_token}
        )

        assert response.json()["refresh_token"] != refresh_token

    async def test_reuse_locks_out_the_stolen_family(
        self, api_client: AsyncClient
    ) -> None:
        _, refresh_token = await _mobile_session(api_client)
        rotated = await api_client.post(
            "/auth/mobile/refresh", json={"refresh_token": refresh_token}
        )
        await api_client.post(
            "/auth/mobile/refresh", json={"refresh_token": refresh_token}
        )

        response = await api_client.post(
            "/auth/mobile/refresh",
            json={"refresh_token": rotated.json()["refresh_token"]},
        )

        assert response.status_code == 401

    async def test_refresh_rejects_deactivated_user(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        _, refresh_token = await _mobile_session(api_client)
        await db_session.execute(update(User).values(is_active=False))

        response = await api_client.post(
            "/auth/mobile/refresh", json={"refresh_token": refresh_token}
        )

        assert response.status_code == 401

    async def test_refresh_rejects_empty_token(self, api_client: AsyncClient) -> None:
        response = await api_client.post(
            "/auth/mobile/refresh", json={"refresh_token": ""}
        )

        assert response.status_code == 422

    async def test_logout_revokes_both_tokens(self, api_client: AsyncClient) -> None:
        access_token, refresh_token = await _mobile_session(api_client)

        await api_client.post(
            "/auth/mobile/logout",
            json={"refresh_token": refresh_token},
            headers=_bearer(access_token),
        )

        me = await api_client.get("/users/me", headers=_bearer(access_token))
        refreshed = await api_client.post(
            "/auth/mobile/refresh", json={"refresh_token": refresh_token}
        )
        assert (me.status_code, refreshed.status_code) == (401, 401)


class TestCurrentUser:
    async def test_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/users/me")

        assert response.status_code == 401

    async def test_returns_own_account(self, api_client: AsyncClient) -> None:
        access_token, _ = await _mobile_session(api_client)

        response = await api_client.get("/users/me", headers=_bearer(access_token))

        assert response.json()["email"] == EMAIL

    async def test_updates_timezone(self, api_client: AsyncClient) -> None:
        access_token, _ = await _mobile_session(api_client)

        response = await api_client.patch(
            "/users/me",
            json={"timezone": "Europe/London"},
            headers=_bearer(access_token),
        )

        assert response.json()["timezone"] == "Europe/London"

    async def test_password_change_logs_out_everywhere(
        self, api_client: AsyncClient
    ) -> None:
        access_token, refresh_token = await _mobile_session(api_client)

        await api_client.patch(
            "/users/me",
            json={"password": "a-brand-new-passphrase"},
            headers=_bearer(access_token),
        )

        me = await api_client.get("/users/me", headers=_bearer(access_token))
        refreshed = await api_client.post(
            "/auth/mobile/refresh", json={"refresh_token": refresh_token}
        )
        assert (me.status_code, refreshed.status_code) == (401, 401)

    async def test_forbids_reading_other_accounts(
        self, api_client: AsyncClient
    ) -> None:
        access_token, _ = await _mobile_session(api_client)
        me = await api_client.get("/users/me", headers=_bearer(access_token))

        response = await api_client.get(
            f"/users/{me.json()['id']}", headers=_bearer(access_token)
        )

        assert response.status_code == 403


class TestDisplayName:
    async def test_starts_empty(self, api_client: AsyncClient) -> None:
        access_token, _ = await _mobile_session(api_client)

        me = await api_client.get("/users/me", headers=_bearer(access_token))

        assert me.json()["display_name"] is None

    async def test_can_be_set_and_is_trimmed(self, api_client: AsyncClient) -> None:
        access_token, _ = await _mobile_session(api_client)

        response = await api_client.patch(
            "/users/me",
            json={"display_name": "  Ada Lovelace "},
            headers=_bearer(access_token),
        )

        assert response.json()["display_name"] == "Ada Lovelace"

    @pytest.mark.parametrize("name", ["   ", "x" * 101])
    async def test_rejects_blank_or_long_names(
        self, api_client: AsyncClient, name: str
    ) -> None:
        access_token, _ = await _mobile_session(api_client)

        response = await api_client.patch(
            "/users/me", json={"display_name": name}, headers=_bearer(access_token)
        )

        assert response.status_code == 422


class TestDeleteAccount:
    async def _delete(
        self, client: AsyncClient, token: str, password: str = PASSWORD
    ) -> Response:
        return await client.request(
            "DELETE",
            "/users/me",
            json={"password": password},
            headers=_bearer(token),
        )

    async def test_deletes_the_account_and_everything_it_owns(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        access_token, _ = await _mobile_session(api_client)
        headers = _bearer(access_token)
        task = await api_client.post(
            "/tasks",
            json={"title": "T", "steps": ["s"], "due_date": "2099-01-01"},
            headers=headers,
        )
        await api_client.post(
            f"/tasks/{task.json()['id']}/postpone",
            json={"to_date": "2099-01-02", "reason": "stuck"},
            headers=headers,
        )

        response = await self._delete(api_client, access_token)

        remaining = {
            model.__tablename__: await db_session.scalar(
                select(func.count()).select_from(model)
            )
            for model in (User, Goal, Task, TaskStep, Notification, RefreshToken)
        }
        assert response.status_code == 204
        assert set(remaining.values()) == {0}

    async def test_signs_the_user_out(self, api_client: AsyncClient) -> None:
        access_token, refresh_token = await _mobile_session(api_client)

        await self._delete(api_client, access_token)

        me = await api_client.get("/users/me", headers=_bearer(access_token))
        refreshed = await api_client.post(
            "/auth/mobile/refresh", json={"refresh_token": refresh_token}
        )
        assert (me.status_code, refreshed.status_code) == (401, 401)

    async def test_clears_the_web_refresh_cookie(self, api_client: AsyncClient) -> None:
        access_token, _ = await _web_session(api_client)

        response = await self._delete(api_client, access_token)

        assert REFRESH_COOKIE in response.headers["set-cookie"]
        assert REFRESH_COOKIE not in api_client.cookies

    async def test_refuses_a_wrong_password(self, api_client: AsyncClient) -> None:
        access_token, _ = await _mobile_session(api_client)

        response = await self._delete(api_client, access_token, "not-my-password")

        me = await api_client.get("/users/me", headers=_bearer(access_token))
        assert (response.status_code, me.status_code) == (400, 200)

    async def test_requires_a_password(self, api_client: AsyncClient) -> None:
        access_token, _ = await _mobile_session(api_client)

        response = await api_client.request(
            "DELETE", "/users/me", json={}, headers=_bearer(access_token)
        )

        assert response.status_code == 422

    async def test_requires_authentication(self, api_client: AsyncClient) -> None:
        response = await api_client.request(
            "DELETE", "/users/me", json={"password": PASSWORD}
        )

        assert response.status_code == 401

    async def test_leaves_other_accounts_alone(
        self, api_client: AsyncClient, other_headers: dict[str, str]
    ) -> None:
        access_token, _ = await _mobile_session(api_client)

        await self._delete(api_client, access_token)

        me = await api_client.get("/users/me", headers=other_headers)
        assert me.status_code == 200
