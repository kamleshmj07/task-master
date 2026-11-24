"""Request and response schemas for accounts and tokens."""

import uuid
from typing import Annotated, Literal
from zoneinfo import available_timezones

from fastapi_users import schemas
from pydantic import AfterValidator, BaseModel, Field, StringConstraints

TIMEZONES = frozenset(available_timezones())


def _validate_timezone(value: str) -> str:
    """Accept only IANA timezone names, e.g. "Europe/London"."""
    if value not in TIMEZONES:
        raise ValueError("Unknown timezone")
    return value


Timezone = Annotated[str, AfterValidator(_validate_timezone)]
DisplayName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class UserRead(schemas.BaseUser[uuid.UUID]):
    """Public view of an account."""

    timezone: str
    display_name: str | None


class UserCreate(schemas.BaseUserCreate):
    """Registration payload."""

    timezone: Timezone = "UTC"
    display_name: DisplayName | None = None


class UserUpdate(schemas.BaseUserUpdate):
    """Partial account update.

    Changing the email or password needs `current_password`, so a stolen
    session cannot take the account over.
    """

    timezone: Timezone | None = None
    display_name: DisplayName | None = None
    current_password: str | None = Field(default=None, max_length=128)


class AccessTokenResponse(BaseModel):
    """Access token for web clients; the refresh token travels in a cookie."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - not a secret
    expires_in: int


class TokenPairResponse(AccessTokenResponse):
    """Access and refresh tokens for mobile clients, which store both."""

    refresh_token: str


class DeleteAccountRequest(BaseModel):
    """The current password, so a stolen session cannot delete the account."""

    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Refresh token sent by mobile clients."""

    refresh_token: str = Field(min_length=1, max_length=128)
