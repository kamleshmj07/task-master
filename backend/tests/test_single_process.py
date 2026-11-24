"""Tests that production refuses a second API process."""

import pytest

from task_master.database import create_engine
from task_master.single_process import SecondProcessError, hold_single_process_lock

pytestmark = [pytest.mark.anyio, pytest.mark.db]


async def test_a_second_process_is_refused(migrated_db: str) -> None:
    first_engine = create_engine(migrated_db)
    second_engine = create_engine(migrated_db)
    lock = await hold_single_process_lock(first_engine)
    try:
        with pytest.raises(SecondProcessError):
            await hold_single_process_lock(second_engine)
    finally:
        await lock.close()
        await first_engine.dispose()
        await second_engine.dispose()


async def test_the_lock_is_free_again_once_released(migrated_db: str) -> None:
    engine = create_engine(migrated_db)
    try:
        await (await hold_single_process_lock(engine)).close()
        again = await hold_single_process_lock(engine)
        await again.close()
    finally:
        await engine.dispose()
