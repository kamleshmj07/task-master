"""Request-scoped dependencies shared by all routes."""

from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from task_master.config import Settings
from task_master.models import utc_now


def get_app_settings(request: Request) -> Settings:
    """Return the settings the running app was built with."""
    settings: Settings = request.app.state.settings
    return settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a database session that is closed when the request ends."""
    session_factory: async_sessionmaker[AsyncSession] = (
        request.app.state.session_factory
    )
    async with session_factory() as session:
        yield session


def get_now() -> datetime:
    """The current time; overridden in tests to pin the date."""
    return utc_now()


def local_today(timezone: str, now: datetime) -> date:
    """The calendar date at `now` in the IANA `timezone`."""
    return now.astimezone(ZoneInfo(timezone)).date()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
NowDep = Annotated[datetime, Depends(get_now)]
