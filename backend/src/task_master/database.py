"""Async database engine and session factory."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


def create_engine(database_url: str, *, pooled: bool = False) -> AsyncEngine:
    """Create an async engine.

    `pooled` is for a database behind a transaction-mode pooler (PgBouncer,
    as with Neon's pooled connection on serverless hosting): the pooler
    already shares connections, so keep no pool of our own, and turn off
    asyncpg's prepared-statement cache, which the pooler cannot share between
    clients. Otherwise keep a normal pool that checks connections before use.
    """
    if pooled:
        return create_async_engine(
            database_url,
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
            },
        )
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory that keeps objects usable after commit."""
    return async_sessionmaker(engine, expire_on_commit=False)
