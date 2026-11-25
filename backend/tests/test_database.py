"""Tests for the database engine, with and without an external pooler."""

import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from task_master.database import create_engine

pytestmark = pytest.mark.anyio

URL = "postgresql+asyncpg://u:p@localhost/db"


class TestCreateEngine:
    async def test_keeps_its_own_pool_by_default(self) -> None:
        engine = create_engine(URL)

        assert not isinstance(engine.pool, NullPool)
        await engine.dispose()

    async def test_keeps_no_pool_behind_a_pooler(self) -> None:
        engine = create_engine(URL, pooled=True)

        assert isinstance(engine.pool, NullPool)
        await engine.dispose()

    @pytest.mark.db
    async def test_pooled_engine_runs_repeated_queries(self, migrated_db: str) -> None:
        # Without a statement cache, the same query works on fresh connections.
        engine = create_engine(migrated_db, pooled=True)
        try:
            async with engine.connect() as connection:
                first = await connection.scalar(text("SELECT 1"))
            async with engine.connect() as connection:
                second = await connection.scalar(text("SELECT 1"))
        finally:
            await engine.dispose()

        assert (first, second) == (1, 1)
