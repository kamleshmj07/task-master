"""Request and response schemas for accounts and tokens."""

import uuid
from typing import Annotated, Literal
from zoneinfo import available_timezones

from fastapi_users import schemas
from pydantic import AfterValidator, BaseModel, Field

TIMEZONES = frozenset(available_timezones())


def _validate_timezone(value: str) -> str:
    """Accept only IANA timezone names, e.g. "Europe/London"."""
    if value not in TIMEZONES:
        raise ValueError("Unknown timezone")
    return value


Timezone = Annotated[str, AfterValidator(_validate_timezone)]


class UserRead(schemas.BaseUser[uuid.UUID]):
    """Public view of an account."""

    timezone: str


class UserCreate(schemas.BaseUserCreate):
    """Registration payload."""

    timezone: Timezone = "UTC"


class UserUpdate(schemas.BaseUserUpdate):
    """Partial account update."""

    timezone: Timezone | None = None


class AccessTokenResponse(BaseModel):
    """Access token for web clients; the refresh token travels in a cookie."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - not a secret
    expires_in: int


class TokenPairResponse(AccessTokenResponse):
    """Access and refresh tokens for mobile clients, which store both."""

    refresh_token: str


class RefreshRequest(BaseModel):
    """Refresh token sent by mobile clients."""

    refresh_token: str = Field(min_length=1, max_length=128)
