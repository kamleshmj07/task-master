"""Migration tests: schema shape, model parity, and reversibility."""

from collections.abc import Callable
from datetime import date
from typing import Any

import anyio
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from task_master.models import Base

pytestmark = pytest.mark.db

MVP_TABLES = {
    "user",
    "goal",
    "task",
    "task_postponement",
    "daily_plan",
    "daily_plan_item",
    "routine",
    "routine_completion",
    "task_step",
}


def _run_on_db[T](url: str, fn: Callable[[Connection], T]) -> T:
    """Run a sync inspection function on an async connection to `url`."""

    async def run() -> T:
        engine = create_async_engine(url)
        async with engine.connect() as connection:
            result = await connection.run_sync(fn)
        await engine.dispose()
        return result

    return anyio.run(run)


def _table_names(connection: Connection) -> set[str]:
    return set(inspect(connection).get_table_names())


BEFORE_REASONS = "af280e9918d3"
OLD_TO_NEW_REASON = {
    "unclear": "stuck",
    "too_big": "stuck",
    "boring": "dreading",
    "anxious": "dreading",
    "blocked": "blocked",
    "no_time": "blocked",
}
SEED_USER_ID = "00000000-0000-4000-8000-000000000001"


def _seed_task(connection: Connection) -> None:
    """Insert one user, goal and task with raw SQL valid at any revision."""
    statements = [
        'INSERT INTO "user" (id, email, hashed_password, is_active,'
        " is_superuser, is_verified, timezone, daily_capacity_minutes)"
        " VALUES (:user, 'seed@example.com', 'x', true, false, false, 'UTC', 480)",
        "INSERT INTO goal (id, user_id, title, status)"
        " VALUES (:goal, :user, 'Seed goal', 'active')",
        "INSERT INTO task (id, user_id, goal_id, title, next_action, status,"
        " postpone_count) VALUES (:task, :user, :goal, 'Seed', 'Start', 'todo', 0)",
    ]
    ids = {
        "user": SEED_USER_ID,
        "goal": "00000000-0000-4000-8000-000000000002",
        "task": "00000000-0000-4000-8000-000000000003",
    }
    for statement in statements:
        connection.execute(text(statement), ids)


def _seed_postponements(reasons: list[str]) -> Callable[[Connection], None]:
    def seed(connection: Connection) -> None:
        _seed_task(connection)
        for index, reason in enumerate(reasons, start=1):
            connection.execute(
                text(
                    "INSERT INTO task_postponement (id, task_id, to_date, reason)"
                    " VALUES (gen_random_uuid(), :task, :to_date, :reason)"
                ),
                {
                    "task": "00000000-0000-4000-8000-000000000003",
                    "to_date": date(2026, 12, index),
                    "reason": reason,
                },
            )
        connection.commit()

    return seed


def _reasons_by_date(connection: Connection) -> list[str]:
    rows = connection.execute(
        text("SELECT reason FROM task_postponement ORDER BY to_date")
    )
    return list(rows.scalars())


def _delete_seed(connection: Connection) -> None:
    connection.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": SEED_USER_ID})
    connection.commit()


def _model_diff(connection: Connection) -> list[Any]:
    return compare_metadata(MigrationContext.configure(connection), Base.metadata)


class TestMigrations:
    def test_upgrade_creates_mvp_tables(self, migrated_db: str) -> None:
        tables = _run_on_db(migrated_db, _table_names)

        assert tables >= MVP_TABLES

    def test_models_match_migrations(self, migrated_db: str) -> None:
        diff = _run_on_db(migrated_db, _model_diff)

        assert diff == []

    def test_downgrade_removes_all_tables(
        self, migrated_db: str, alembic_config: Config
    ) -> None:
        command.downgrade(alembic_config, "base")
        try:
            tables = _run_on_db(migrated_db, _table_names)
        finally:
            command.upgrade(alembic_config, "head")

        assert tables == {"alembic_version"}


class TestSimplifyPostponeReasons:
    def test_upgrade_maps_old_reasons_to_root_causes(
        self, migrated_db: str, alembic_config: Config
    ) -> None:
        command.downgrade(alembic_config, BEFORE_REASONS)
        try:
            _run_on_db(migrated_db, _seed_postponements(list(OLD_TO_NEW_REASON)))
            command.upgrade(alembic_config, "head")
            reasons = _run_on_db(migrated_db, _reasons_by_date)
        finally:
            _run_on_db(migrated_db, _delete_seed)
            command.upgrade(alembic_config, "head")

        assert reasons == list(OLD_TO_NEW_REASON.values())

    def test_downgrade_maps_new_reasons_back(
        self, migrated_db: str, alembic_config: Config
    ) -> None:
        new_reasons = ["stuck", "dreading", "blocked"]
        # The raw-SQL seed matches the schema before steps replaced next_action.
        command.downgrade(alembic_config, BEFORE_STEPS)
        try:
            _run_on_db(migrated_db, _seed_postponements(new_reasons))
            command.downgrade(alembic_config, BEFORE_REASONS)
            reasons = _run_on_db(migrated_db, _reasons_by_date)
        finally:
            _run_on_db(migrated_db, _delete_seed)
            command.upgrade(alembic_config, "head")

        assert reasons == ["unclear", "boring", "blocked"]


class TestDefaultGoalBackfill:
    def test_upgrade_gives_existing_users_the_default_goal(
        self, migrated_db: str, alembic_config: Config
    ) -> None:
        command.downgrade(alembic_config, BEFORE_ROUTINES)
        try:
            _run_on_db(migrated_db, _seed_user)
            command.upgrade(alembic_config, "head")
            titles = _run_on_db(migrated_db, _seed_goal_titles)
        finally:
            _run_on_db(migrated_db, _delete_seed)
            command.upgrade(alembic_config, "head")

        assert sorted(titles) == ["Essentials", "Seed goal"]


BEFORE_ROUTINES = "e04dfba4791d"
BEFORE_STEPS = "c2497c12038c"


def _seed_user(connection: Connection) -> None:
    _seed_task(connection)
    connection.commit()


def _seed_goal_titles(connection: Connection) -> list[str]:
    rows = connection.execute(
        text("SELECT title FROM goal WHERE user_id = :id"), {"id": SEED_USER_ID}
    )
    return list(rows.scalars())


class TestTaskSteps:
    def test_upgrade_turns_next_action_into_first_step(
        self, migrated_db: str, alembic_config: Config
    ) -> None:
        command.downgrade(alembic_config, BEFORE_STEPS)
        try:
            _run_on_db(migrated_db, _seed_user)
            command.upgrade(alembic_config, "head")
            steps = _run_on_db(migrated_db, _seed_step_texts)
        finally:
            _run_on_db(migrated_db, _delete_seed)
            command.upgrade(alembic_config, "head")

        assert steps == ["Start"]


def _seed_step_texts(connection: Connection) -> list[str]:
    rows = connection.execute(
        text(
            "SELECT s.text FROM task_step s JOIN task t ON t.id = s.task_id"
            " WHERE t.user_id = :id ORDER BY s.position"
        ),
        {"id": SEED_USER_ID},
    )
    return list(rows.scalars())
