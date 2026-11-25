"""Choose a new goal's accent colour."""

import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import Goal, GoalColor, GoalStatus


def least_used_color(used: list[GoalColor]) -> GoalColor:
    """The palette colour that appears least in `used`; earliest on a tie."""
    counts = Counter(used)
    return min(GoalColor, key=lambda color: counts[color])


async def next_goal_color(session: AsyncSession, user_id: uuid.UUID) -> GoalColor:
    """The colour the user's active goals use least, so goals stay apart."""
    used = await session.scalars(
        select(Goal.color).where(
            Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE
        )
    )
    return least_used_color(list(used))
