"""Login, refresh and logout for web and mobile clients.

Both clients send a short-lived access token as `Authorization: Bearer`.
They differ in where the long-lived refresh token lives:

- web: an `HttpOnly`, `Secure`, `SameSite=Strict` cookie scoped to `/auth/web`,
  so page scripts can never read it;
- mobile: the response body, for the app to keep in secure device storage.
"""

import logging
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.exceptions import InvalidID, UserNotExists
from fastapi_users.router.common import ErrorCode

from task_master.auth.lockout import LoginThrottle
from task_master.auth.rate_limit import enforce_auth_rate_limit
from task_master.auth.reauth import (
    WrongPasswordError,
    check_password,
    wrong_password_reason,
)
from task_master.auth.schemas import (
    AccessTokenResponse,
    DeleteAccountRequest,
    RefreshRequest,
    TokenPairResponse,
)
from task_master.auth.tokens import (
    InvalidRefreshTokenError,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from task_master.auth.users import (
    CurrentUserDep,
    CurrentUserTokenDep,
    StrategyDep,
    UserManagerDep,
)
from task_master.config import Settings
from task_master.dependencies import SessionDep, SettingsDep
from task_master.models import User, utc_now

logger = logging.getLogger(__name__)

WEB_PREFIX = "/auth/web"
REFRESH_COOKIE = "refresh_token"

CredentialsDep = Annotated[OAuth2PasswordRequestForm, Depends()]
RateLimitDep = Depends(enforce_auth_rate_limit)

web_router = APIRouter(prefix=WEB_PREFIX, tags=["auth: web"])
account_router = APIRouter(prefix="/users", tags=["users"])
mobile_router = APIRouter(prefix="/auth/mobile", tags=["auth: mobile"])


def _refresh_lifetime(settings: Settings) -> timedelta:
    return timedelta(days=settings.refresh_token_lifetime_days)


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
    )


async def _authenticate(
    request: Request, credentials: CredentialsDep, users: UserManagerDep
) -> User:
    """Return the active user matching the credentials.

    Raises 429 while the account or client IP is locked out (without checking
    the password) and 400 for bad credentials, counting the failure.
    """
    throttle: LoginThrottle = request.app.state.login_throttle
    ip = request.client.host if request.client else "unknown"
    email = credentials.username
    wait = await throttle.retry_after(ip, email)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed logins; try again later",
            headers={"Retry-After": str(wait)},
        )
    user = await users.authenticate(credentials)
    if user is None or not user.is_active:
        await throttle.record_failure(ip, email)
        logger.warning("Failed login attempt")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.LOGIN_BAD_CREDENTIALS,
        )
    await throttle.record_success(email)
    return user


async def _rotate(
    refresh_token: str,
    users: UserManagerDep,
    session: SessionDep,
    settings: Settings,
) -> tuple[User, str]:
    """Spend a refresh token; return its active owner and the replacement."""
    try:
        user_id, replacement = await rotate_refresh_token(
            session, refresh_token, _refresh_lifetime(settings)
        )
        user = await users.get(user_id)
    except InvalidRefreshTokenError, UserNotExists, InvalidID:
        raise _invalid_refresh_token() from None
    if not user.is_active:
        raise _invalid_refresh_token()
    return user, replacement


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=int(_refresh_lifetime(settings).total_seconds()),
        path=WEB_PREFIX,
        secure=True,
        httponly=True,
        samesite="strict",
    )


def _access_response(token: str, settings: Settings) -> AccessTokenResponse:
    return AccessTokenResponse(
        access_token=token, expires_in=settings.access_token_lifetime_seconds
    )


def _pair_response(
    access_token: str, refresh_token: str, settings: Settings
) -> TokenPairResponse:
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_lifetime_seconds,
    )


async def _new_refresh_token(
    session: SessionDep, user_id: uuid.UUID, settings: Settings
) -> str:
    return await issue_refresh_token(session, user_id, _refresh_lifetime(settings))


@web_router.post("/login")
async def handle_web_login(
    response: Response,
    user: Annotated[User, Depends(_authenticate)],
    strategy: StrategyDep,
    session: SessionDep,
    settings: SettingsDep,
) -> AccessTokenResponse:
    """Log in; return an access token and set the refresh cookie."""
    access_token = await strategy.write_token(user)
    refresh_token = await _new_refresh_token(session, user.id, settings)
    _set_refresh_cookie(response, refresh_token, settings)
    return _access_response(access_token, settings)


@web_router.post("/refresh", dependencies=[RateLimitDep])
async def handle_web_refresh(
    response: Response,
    users: UserManagerDep,
    strategy: StrategyDep,
    session: SessionDep,
    settings: SettingsDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> AccessTokenResponse:
    """Swap the refresh cookie for a new access token and cookie."""
    if not refresh_token:
        raise _invalid_refresh_token()
    user, replacement = await _rotate(refresh_token, users, session, settings)
    _set_refresh_cookie(response, replacement, settings)
    return _access_response(await strategy.write_token(user), settings)


@web_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def handle_web_logout(
    response: Response,
    user_token: CurrentUserTokenDep,
    strategy: StrategyDep,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> None:
    """Revoke the access token and refresh cookie, and clear the cookie."""
    user, access_token = user_token
    await strategy.destroy_token(access_token, user)
    if refresh_token:
        await revoke_refresh_token(session, user.id, refresh_token)
    response.delete_cookie(
        REFRESH_COOKIE, path=WEB_PREFIX, secure=True, httponly=True, samesite="strict"
    )


@mobile_router.post("/login")
async def handle_mobile_login(
    user: Annotated[User, Depends(_authenticate)],
    strategy: StrategyDep,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenPairResponse:
    """Log in; return access and refresh tokens."""
    access_token = await strategy.write_token(user)
    refresh_token = await _new_refresh_token(session, user.id, settings)
    return _pair_response(access_token, refresh_token, settings)


@mobile_router.post("/refresh", dependencies=[RateLimitDep])
async def handle_mobile_refresh(
    body: RefreshRequest,
    users: UserManagerDep,
    strategy: StrategyDep,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenPairResponse:
    """Swap a refresh token for a new access and refresh token pair."""
    user, replacement = await _rotate(body.refresh_token, users, session, settings)
    access_token = await strategy.write_token(user)
    return _pair_response(access_token, replacement, settings)


@mobile_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def handle_mobile_logout(
    body: RefreshRequest,
    user_token: CurrentUserTokenDep,
    strategy: StrategyDep,
    session: SessionDep,
) -> None:
    """Revoke the access token and the refresh token's family."""
    user, access_token = user_token
    await strategy.destroy_token(access_token, user)
    await revoke_refresh_token(session, user.id, body.refresh_token)


@account_router.delete(
    "/me", status_code=status.HTTP_204_NO_CONTENT, dependencies=[RateLimitDep]
)
async def handle_delete_account(
    body: DeleteAccountRequest,
    response: Response,
    user: CurrentUserDep,
    users: UserManagerDep,
) -> None:
    """Delete the account and everything it owns, after re-checking the password.

    Goals, tasks, steps, postponements, routines, plans, notifications and
    every session go with it; the web refresh cookie is cleared.
    """
    try:
        await check_password(
            users.session, users.password_helper, user, body.password, utc_now()
        )
    except WrongPasswordError as error:
        logger.warning("Account deletion refused: wrong password")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=wrong_password_reason(error).replace("Current password", "Password"),
        ) from error
    await users.delete(user)
    logger.info("Account deleted")
    response.delete_cookie(
        REFRESH_COOKIE, path=WEB_PREFIX, secure=True, httponly=True, samesite="strict"
    )
