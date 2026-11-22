"""Query helpers that scope every lookup to the requesting user."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import Goal, Routine, Task

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


async def get_owned_or_404[M: (Goal, Routine, Task)](
    session: AsyncSession, model: type[M], id: uuid.UUID, user_id: uuid.UUID
) -> M:
    """Return the row with `id` owned by `user_id`.

    Rows owned by someone else are reported as missing, so ids of other
    users' data are never confirmed.
    """
    statement = select(model).where(model.id == id, model.user_id == user_id)
    row = await session.scalar(statement)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} not found",
        )
    return row
