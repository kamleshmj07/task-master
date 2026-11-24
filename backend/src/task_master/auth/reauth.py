"""Re-checking the password before account changes, with a guessing limit.

Changing the email or password and deleting the account all ask for the
current password, so a stolen session alone cannot take the account over.
Those checks are limited too: after `MAX_FAILURES` wrong passwords in a row
they are refused for `LOCK_DURATION`, even with the right password. A correct
password resets the count, and so does a password reset.

The count lives on the user row, so restarts do not wipe it.
"""

import logging
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from fastapi_users.password import PasswordHelperProtocol
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import User

logger = logging.getLogger(__name__)

MAX_FAILURES = 5
LOCK_DURATION = timedelta(hours=24)


class WrongPasswordError(Exception):
    """The password was wrong; `remaining` tries are left before the lock."""

    def __init__(self, remaining: int) -> None:
        super().__init__("Password is incorrect")
        self.remaining = remaining


async def check_password(
    session: AsyncSession,
    helper: PasswordHelperProtocol,
    user: User,
    password: str,
    now: datetime,
) -> None:
    """Verify `password`, counting wrong ones; refuse while the lock holds.

    Raises 429 while locked, and `WrongPasswordError` for a wrong password.
    """
    locked_until = user.password_check_locked_until
    if locked_until is not None and locked_until > now:
        raise locked_error(locked_until)
    verified, _ = helper.verify_and_update(password, user.hashed_password)
    if verified:
        await _reset(session, user)
        return
    failures = user.password_check_failures + 1
    if failures >= MAX_FAILURES:
        user.password_check_failures = 0
        user.password_check_locked_until = now + LOCK_DURATION
        await session.commit()
        logger.warning(
            "Password checks locked after repeated wrong passwords",
            extra={"event": "password_check_locked"},
        )
        raise locked_error(now + LOCK_DURATION)
    user.password_check_failures = failures
    await session.commit()
    raise WrongPasswordError(remaining=MAX_FAILURES - failures)


async def clear_password_check_lock(session: AsyncSession, user: User) -> None:
    """Forget wrong attempts, e.g. after the password was reset."""
    await _reset(session, user)


async def _reset(session: AsyncSession, user: User) -> None:
    if user.password_check_failures == 0 and user.password_check_locked_until is None:
        return
    user.password_check_failures = 0
    user.password_check_locked_until = None
    await session.commit()


def locked_error(until: datetime) -> HTTPException:
    """429 saying when checks are allowed again."""
    seconds = max(1, int((until - datetime.now(until.tzinfo)).total_seconds()))
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            "Too many wrong passwords. For your safety, changing your email or "
            "password and deleting the account are paused for 24 hours."
        ),
        headers={"Retry-After": str(seconds)},
    )


def wrong_password_reason(error: WrongPasswordError) -> str:
    """What to tell the user about a wrong password and the tries left."""
    tries = "1 more try" if error.remaining == 1 else f"{error.remaining} more tries"
    return f"Current password is incorrect. {tries} before a 24-hour pause."
