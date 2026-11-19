"""Builders for persisted model instances used in DB tests."""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import DailyPlan, Goal, Task, User


async def make_user(session: AsyncSession, email: str | None = None) -> User:
    """Persist a user with a unique email."""
    user = User(
        email=email or f"{uuid.uuid4().hex}@example.com",
        hashed_password="not-a-real-hash",
    )
    session.add(user)
    await session.flush()
    return user


async def make_goal(session: AsyncSession, user: User) -> Goal:
    """Persist a goal owned by `user`."""
    goal = Goal(user_id=user.id, title="Ship the MVP", why="Users are waiting")
    session.add(goal)
    await session.flush()
    return goal


async def make_task(session: AsyncSession, goal: Goal) -> Task:
    """Persist a task under `goal`, owned by the goal's owner."""
    task = Task(
        user_id=goal.user_id,
        goal_id=goal.id,
        title="Write the schema",
        next_action="Open models.py and add the User class",
        estimate_minutes=25,
    )
    session.add(task)
    await session.flush()
    return task


async def make_plan(session: AsyncSession, user: User, plan_date: date) -> DailyPlan:
    """Persist a daily plan for `user` on `plan_date`."""
    plan = DailyPlan(user_id=user.id, plan_date=plan_date)
    session.add(plan)
    await session.flush()
    return plan
