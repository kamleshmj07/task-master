"""DB tests for refresh token rotation and session revocation."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.auth.tokens import (
    InvalidRefreshTokenError,
    hash_token,
    issue_refresh_token,
    revoke_refresh_token,
    revoke_user_sessions,
    rotate_refresh_token,
)
from task_master.models import AccessToken, RefreshToken
from tests.factories import make_user

pytestmark = [pytest.mark.anyio, pytest.mark.db]

LIFETIME = timedelta(days=1)


async def _stored(session: AsyncSession, token: str) -> RefreshToken:
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(token))
    )
    assert row is not None
    return row


class TestIssue:
    async def test_stores_only_the_hash(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)

        token = await issue_refresh_token(db_session, user.id, LIFETIME)

        stored = await _stored(db_session, token)
        assert stored.token_hash != token


class TestRotate:
    async def test_returns_owner_and_new_token(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)
        token = await issue_refresh_token(db_session, user.id, LIFETIME)

        user_id, replacement = await rotate_refresh_token(db_session, token, LIFETIME)

        assert (user_id, replacement != token) == (user.id, True)

    async def test_keeps_the_family(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)
        token = await issue_refresh_token(db_session, user.id, LIFETIME)

        _, replacement = await rotate_refresh_token(db_session, token, LIFETIME)

        old, new = (
            await _stored(db_session, token),
            await _stored(db_session, replacement),
        )
        assert old.family_id == new.family_id

    async def test_rejects_unknown_token(self, db_session: AsyncSession) -> None:
        with pytest.raises(InvalidRefreshTokenError):
            await rotate_refresh_token(db_session, "unknown", LIFETIME)

    async def test_rejects_expired_token(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)
        token = await issue_refresh_token(db_session, user.id, timedelta(seconds=-1))

        with pytest.raises(InvalidRefreshTokenError):
            await rotate_refresh_token(db_session, token, LIFETIME)

    async def test_reuse_revokes_the_whole_family(
        self, db_session: AsyncSession
    ) -> None:
        user = await make_user(db_session)
        token = await issue_refresh_token(db_session, user.id, LIFETIME)
        _, replacement = await rotate_refresh_token(db_session, token, LIFETIME)

        with pytest.raises(InvalidRefreshTokenError):
            await rotate_refresh_token(db_session, token, LIFETIME)

        with pytest.raises(InvalidRefreshTokenError):
            await rotate_refresh_token(db_session, replacement, LIFETIME)


class TestRevoke:
    async def test_revokes_family_on_logout(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)
        token = await issue_refresh_token(db_session, user.id, LIFETIME)

        await revoke_refresh_token(db_session, user.id, token)

        assert (await _stored(db_session, token)).revoked_at is not None

    async def test_ignores_token_of_another_user(
        self, db_session: AsyncSession
    ) -> None:
        owner, other = await make_user(db_session), await make_user(db_session)
        token = await issue_refresh_token(db_session, owner.id, LIFETIME)

        await revoke_refresh_token(db_session, other.id, token)

        assert (await _stored(db_session, token)).revoked_at is None

    async def test_ignores_unknown_token(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)

        await revoke_refresh_token(db_session, user.id, "unknown")

    async def test_revoke_user_sessions_clears_everything(
        self, db_session: AsyncSession
    ) -> None:
        user = await make_user(db_session)
        refresh = await issue_refresh_token(db_session, user.id, LIFETIME)
        db_session.add(AccessToken(token="a" * 43, user_id=user.id))
        await db_session.flush()

        await revoke_user_sessions(db_session, user.id)

        access_count = await db_session.scalar(
            select(func.count()).select_from(AccessToken)
        )
        stored = await _stored(db_session, refresh)
        assert (access_count, stored.revoked_at is not None) == (0, True)
