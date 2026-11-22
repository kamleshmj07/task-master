"""SQLAlchemy adapters implementing fastapi-users' storage interfaces.

Written in-house instead of using `fastapi-users-db-sqlalchemy`, which pins
SQLAlchemy below 2.1 and is no longer actively released.
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi_users.db import BaseUserDatabase
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import AccessToken, User


class UserDatabase(BaseUserDatabase[User, uuid.UUID]):
    """User storage for fastapi-users. OAuth accounts are not supported."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: uuid.UUID) -> User | None:
        """Return the user with `id`, if any."""
        return await self.session.get(User, id)

    async def get_by_email(self, email: str) -> User | None:
        """Return the user with `email`, compared case-insensitively."""
        statement = select(User).where(func.lower(User.email) == email.lower())
        return await self.session.scalar(statement)

    async def create(self, create_dict: dict[str, Any]) -> User:
        """Persist a new user."""
        user = User(**create_dict)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user: User, update_dict: dict[str, Any]) -> User:
        """Apply `update_dict` to `user` and persist it."""
        for key, value in update_dict.items():
            setattr(user, key, value)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        """Delete `user` and, by cascade, everything they own."""
        await self.session.delete(user)
        await self.session.commit()


class AccessTokenDatabase:
    """Access token storage for fastapi-users' `DatabaseStrategy`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_token(
        self, token: str, max_age: datetime | None = None
    ) -> AccessToken | None:
        """Return the token row, ignoring tokens created before `max_age`."""
        statement = select(AccessToken).where(AccessToken.token == token)
        if max_age is not None:
            statement = statement.where(AccessToken.created_at >= max_age)
        return await self.session.scalar(statement)

    async def create(self, create_dict: dict[str, Any]) -> AccessToken:
        """Persist a new access token."""
        access_token = AccessToken(**create_dict)
        self.session.add(access_token)
        await self.session.commit()
        return access_token

    async def update(
        self, access_token: AccessToken, update_dict: dict[str, Any]
    ) -> AccessToken:
        """Apply `update_dict` to `access_token` and persist it."""
        for key, value in update_dict.items():
            setattr(access_token, key, value)
        await self.session.commit()
        return access_token

    async def delete(self, access_token: AccessToken) -> None:
        """Delete (revoke) `access_token`."""
        await self.session.delete(access_token)
        await self.session.commit()
