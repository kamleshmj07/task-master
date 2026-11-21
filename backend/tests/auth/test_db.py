"""DB tests for the fastapi-users storage adapters."""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.auth.db import AccessTokenDatabase, UserDatabase
from task_master.models import utc_now
from tests.factories import make_user

pytestmark = [pytest.mark.anyio, pytest.mark.db]


class TestUserDatabase:
    async def test_creates_user(self, db_session: AsyncSession) -> None:
        user_db = UserDatabase(db_session)

        user = await user_db.create(
            {"email": "new@example.com", "hashed_password": "hash"}
        )

        assert await user_db.get(user.id) is user

    async def test_finds_email_case_insensitively(
        self, db_session: AsyncSession
    ) -> None:
        user = await make_user(db_session, email="Mixed@Example.com")

        found = await UserDatabase(db_session).get_by_email("mixed@example.COM")

        assert found is user

    async def test_returns_none_for_unknown_email(
        self, db_session: AsyncSession
    ) -> None:
        assert await UserDatabase(db_session).get_by_email("no@example.com") is None

    async def test_updates_fields(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)

        await UserDatabase(db_session).update(user, {"daily_capacity_minutes": 300})

        assert user.daily_capacity_minutes == 300

    async def test_deletes_user(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)
        user_db = UserDatabase(db_session)

        await user_db.delete(user)

        assert await user_db.get(user.id) is None


class TestAccessTokenDatabase:
    async def test_finds_created_token(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)
        token_db = AccessTokenDatabase(db_session)
        await token_db.create({"token": "t" * 43, "user_id": user.id})

        found = await token_db.get_by_token("t" * 43)

        assert found is not None and found.user_id == user.id

    async def test_ignores_token_older_than_max_age(
        self, db_session: AsyncSession
    ) -> None:
        user = await make_user(db_session)
        token_db = AccessTokenDatabase(db_session)
        old = utc_now() - timedelta(hours=1)
        await token_db.create(
            {"token": "t" * 43, "user_id": user.id, "created_at": old}
        )

        found = await token_db.get_by_token("t" * 43, max_age=utc_now())

        assert found is None

    async def test_deleted_token_is_gone(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)
        token_db = AccessTokenDatabase(db_session)
        token = await token_db.create({"token": "t" * 43, "user_id": user.id})

        await token_db.delete(token)

        assert await token_db.get_by_token("t" * 43) is None
