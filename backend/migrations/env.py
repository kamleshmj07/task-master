"""Alembic migration environment (async, driven by app settings)."""

from logging.config import fileConfig

import anyio
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from task_master.config import get_settings
from task_master.models import Base

config = context.config

if config.config_file_name is not None and config.attributes.get(
    "configure_logger", True
):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Prefer a URL set on the Alembic config (tests), else app settings."""
    url = config.get_main_option("sqlalchemy.url")
    return url or get_settings().database_url.get_secret_value()


def run_migrations_offline() -> None:
    """Emit migration SQL to stdout without a database connection."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations on an open connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Open an async connection and run migrations through it."""
    engine = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    anyio.run(run_async_migrations)
