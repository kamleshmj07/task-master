"""Refresh token issue, rotation and revocation.

Each refresh token is single use. Refreshing spends it and issues a new one in
the same family. Presenting a spent token means it was stolen or replayed, so
the whole family is revoked and its holder must log in again.
"""

import hashlib
import logging
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import AccessToken, RefreshToken, utc_now

logger = logging.getLogger(__name__)

REFRESH_TOKEN_BYTES = 32


class InvalidRefreshTokenError(Exception):
    """The refresh token is unknown, expired or already spent."""


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest stored in place of the token."""
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_refresh_token(
    session: AsyncSession,
    user_id: uuid.UUID,
    lifetime: timedelta,
    family_id: uuid.UUID | None = None,
) -> str:
    """Persist a new refresh token and return its raw value."""
    token = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
    session.add(
        RefreshToken(
            user_id=user_id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_token(token),
            expires_at=utc_now() + lifetime,
        )
    )
    await session.commit()
    return token


async def rotate_refresh_token(
    session: AsyncSession, token: str, lifetime: timedelta
) -> tuple[uuid.UUID, str]:
    """Spend `token` and return its owner with a replacement token.

    Raises `InvalidRefreshTokenError` if the token cannot be used.
    """
    statement = (
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(token))
        .with_for_update()
    )
    current = await session.scalar(statement)
    if current is None:
        raise InvalidRefreshTokenError
    if current.revoked_at is not None:
        logger.warning("Refresh token reuse detected; revoking its family")
        await _revoke_family(session, current.family_id)
        await session.commit()
        raise InvalidRefreshTokenError
    if current.expires_at <= utc_now():
        raise InvalidRefreshTokenError
    current.revoked_at = utc_now()
    replacement = await issue_refresh_token(
        session, current.user_id, lifetime, current.family_id
    )
    return current.user_id, replacement


async def revoke_refresh_token(
    session: AsyncSession, user_id: uuid.UUID, token: str
) -> None:
    """Revoke the family of `token` if `user_id` owns it. Used on logout."""
    statement = select(RefreshToken.family_id).where(
        RefreshToken.token_hash == hash_token(token),
        RefreshToken.user_id == user_id,
    )
    family_id = await session.scalar(statement)
    if family_id is None:
        return
    await _revoke_family(session, family_id)
    await session.commit()


async def revoke_user_sessions(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Delete every access token and revoke every refresh token of a user."""
    await session.execute(delete(AccessToken).where(AccessToken.user_id == user_id))
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    await session.commit()


async def _revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    """Mark every unrevoked token in a family as revoked."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
