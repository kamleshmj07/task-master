"""fastapi-users wiring: user manager, access-token strategy and current user."""

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi_users import (
    BaseUserManager,
    FastAPIUsers,
    InvalidPasswordException,
    UUIDIDMixin,
)
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
)
from fastapi_users.authentication.strategy import DatabaseStrategy
from fastapi_users.schemas import BaseUserCreate, BaseUserUpdate
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.auth.db import AccessTokenDatabase, UserDatabase
from task_master.auth.reauth import (
    WrongPasswordError,
    check_password,
    clear_password_check_lock,
    wrong_password_reason,
)
from task_master.auth.tokens import revoke_user_sessions
from task_master.defaults import DEFAULT_GOAL_TITLE, DEFAULT_GOAL_WHY
from task_master.dependencies import SessionDep, SettingsDep
from task_master.models import Goal, User, utc_now

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """Account rules: password policy and session revocation."""

    def __init__(
        self, user_db: UserDatabase, session: AsyncSession, secret: str
    ) -> None:
        super().__init__(user_db)
        self.session = session
        self.reset_password_token_secret = secret
        self.verification_token_secret = secret

    async def validate_password(
        self, password: str, user: BaseUserCreate | User
    ) -> None:
        """Require 12-128 characters that do not contain the email name."""
        if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
            raise InvalidPasswordException(
                reason=(
                    f"Password must be {MIN_PASSWORD_LENGTH}-"
                    f"{MAX_PASSWORD_LENGTH} characters"
                )
            )
        email_name = user.email.split("@", 1)[0].lower()
        if len(email_name) >= 3 and email_name in password.lower():
            raise InvalidPasswordException(
                reason="Password must not contain your email"
            )

    async def update(
        self,
        user_update: BaseUserUpdate,
        user: User,
        safe: bool = False,
        request: Request | None = None,
    ) -> User:
        """Apply an update; email and password changes need the current password."""
        if _changes_credentials(user_update, user):
            current = getattr(user_update, "current_password", None) or ""
            try:
                await check_password(
                    self.session, self.password_helper, user, current, utc_now()
                )
            except WrongPasswordError as error:
                logger.warning(
                    "Credential change refused: wrong current password",
                    extra={"event": "credential_change_refused"},
                )
                raise InvalidPasswordException(
                    reason=wrong_password_reason(error)
                ) from error
        changes = user_update.model_dump(
            exclude_unset=True, exclude={"current_password"}
        )
        return await super().update(
            type(user_update).model_validate(changes), user, safe, request
        )

    async def on_after_reset_password(
        self, user: User, request: Request | None = None
    ) -> None:
        """A reset proves who it is: forget wrong re-check attempts."""
        await clear_password_check_lock(self.session, user)

    async def on_after_register(
        self, user: User, request: Request | None = None
    ) -> None:
        """Start every account with the default goal."""
        self.session.add(
            Goal(user_id=user.id, title=DEFAULT_GOAL_TITLE, why=DEFAULT_GOAL_WHY)
        )
        await self.session.commit()

    async def on_after_update(
        self,
        user: User,
        update_dict: dict[str, Any],
        request: Request | None = None,
    ) -> None:
        """Log the user out everywhere after a password change."""
        if update_dict.get("password") is not None:
            await revoke_user_sessions(self.session, user.id)


def _changes_credentials(user_update: BaseUserUpdate, user: User) -> bool:
    """Whether the update sets a new password or a different email."""
    if user_update.password is not None:
        return True
    return user_update.email is not None and user_update.email != user.email


async def get_user_db(session: SessionDep) -> AsyncIterator[UserDatabase]:
    """Yield user storage bound to the request session."""
    yield UserDatabase(session)


async def get_access_token_db(
    session: SessionDep,
) -> AsyncIterator[AccessTokenDatabase]:
    """Yield access token storage bound to the request session."""
    yield AccessTokenDatabase(session)


async def get_user_manager(
    user_db: Annotated[UserDatabase, Depends(get_user_db)],
    session: SessionDep,
    settings: SettingsDep,
) -> AsyncIterator[UserManager]:
    """Yield the user manager for this request."""
    yield UserManager(user_db, session, settings.auth_secret.get_secret_value())


def get_database_strategy(
    access_token_db: Annotated[AccessTokenDatabase, Depends(get_access_token_db)],
    settings: SettingsDep,
) -> DatabaseStrategy[User, uuid.UUID, Any]:
    """Opaque access tokens stored in the database, so logout revokes them.

    The token type is `Any` because SQLAlchemy's `Mapped` columns do not
    satisfy fastapi-users' `AccessTokenProtocol` structurally.
    """
    return DatabaseStrategy(
        access_token_db, lifetime_seconds=settings.access_token_lifetime_seconds
    )


bearer_transport = BearerTransport(tokenUrl="auth/mobile/login")
auth_backend = AuthenticationBackend[User, uuid.UUID](
    name="database",
    transport=bearer_transport,
    get_strategy=get_database_strategy,
)
fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
current_active_user_token = fastapi_users.authenticator.current_user_token(active=True)

UserManagerDep = Annotated[UserManager, Depends(get_user_manager)]
StrategyDep = Annotated[
    DatabaseStrategy[User, uuid.UUID, Any], Depends(get_database_strategy)
]
CurrentUserDep = Annotated[User, Depends(current_active_user)]
CurrentUserTokenDep = Annotated[tuple[User, str], Depends(current_active_user_token)]
