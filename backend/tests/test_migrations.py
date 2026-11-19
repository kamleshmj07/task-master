"""Migration tests: schema shape, model parity, and reversibility."""

from collections.abc import Callable
from typing import Any

import anyio
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, inspect
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
