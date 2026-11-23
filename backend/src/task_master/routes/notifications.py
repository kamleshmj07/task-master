"""Notification endpoints: goal updates and upcoming tasks, behind the bell."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, update

from task_master.alerts import check_notifications
from task_master.auth.users import CurrentUserDep
from task_master.dependencies import NowDep, SessionDep
from task_master.models import Notification
from task_master.queries import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from task_master.schemas import NotificationRead, UnreadCount

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def handle_list_notifications(
    user: CurrentUserDep,
    session: SessionDep,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[NotificationRead]:
    """The user's notifications, newest first."""
    statement = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    statement = (
        statement.order_by(Notification.created_at.desc(), Notification.id)
        .limit(limit)
        .offset(offset)
    )
    rows = await session.scalars(statement)
    return [NotificationRead.model_validate(row) for row in rows]


@router.post("/check")
async def handle_check_notifications(
    user: CurrentUserDep, session: SessionDep, now: NowDep
) -> UnreadCount:
    """Create any notifications now due, then return the unread count.

    Clients call this when the app opens. Repeating it is harmless: each
    event is notified once.
    """
    await check_notifications(session, user, now)
    return await handle_count_unread(user, session)


@router.get("/unread-count")
async def handle_count_unread(user: CurrentUserDep, session: SessionDep) -> UnreadCount:
    """How many notifications are unread, for the bell's badge."""
    count = await session.scalar(
        select(func.count()).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    )
    return UnreadCount(unread=count or 0)


@router.post("/{notification_id}/read")
async def handle_mark_read(
    notification_id: uuid.UUID, user: CurrentUserDep, session: SessionDep, now: NowDep
) -> NotificationRead:
    """Mark one notification as read. Marking it again changes nothing."""
    notification = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    if notification.read_at is None:
        notification.read_at = now
        await session.commit()
    return NotificationRead.model_validate(notification)


@router.post("/read-all")
async def handle_mark_all_read(
    user: CurrentUserDep, session: SessionDep, now: NowDep
) -> UnreadCount:
    """Mark every unread notification as read."""
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=now)
    )
    await session.commit()
    return UnreadCount(unread=0)
