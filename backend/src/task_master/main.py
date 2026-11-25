"""FastAPI application factory."""

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from task_master.auth import routes as auth_routes
from task_master.auth.lockout import (
    LockoutPolicy,
    LoginThrottle,
    MemoryThrottleStore,
    PostgresThrottleStore,
    ThrottleStore,
)
from task_master.auth.rate_limit import (
    MemoryWindowStore,
    PostgresWindowStore,
    RateLimiter,
    WindowStore,
    enforce_auth_rate_limit,
)
from task_master.auth.schemas import UserCreate, UserRead, UserUpdate
from task_master.auth.users import fastapi_users
from task_master.config import Settings, get_settings
from task_master.database import create_engine, create_session_factory
from task_master.logging_setup import configure_logging
from task_master.routes import (
    goals,
    health,
    notifications,
    onboarding,
    plans,
    postponements,
    routines,
    steps,
    tasks,
)
from task_master.security import install_security


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app with middleware and routes."""
    settings = settings or get_settings()
    engine = create_engine(
        settings.database_url.get_secret_value(), pooled=settings.database_pooled
    )
    prefix = settings.api_prefix

    is_production = settings.environment == "production"

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        try:
            yield
        finally:
            await engine.dispose()

    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        docs_url=None if is_production else f"{prefix}/docs",
        openapi_url=None if is_production else f"{prefix}/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    session_factory = create_session_factory(engine)
    app.state.session_factory = session_factory
    # Production shares counters through Postgres, so it may run any number of
    # API processes; elsewhere each process counts in memory.
    new_window_store: Callable[[], WindowStore] = (
        (lambda: PostgresWindowStore(session_factory))
        if is_production
        else MemoryWindowStore
    )
    throttle_store: ThrottleStore = (
        PostgresThrottleStore(session_factory)
        if is_production
        else MemoryThrottleStore()
    )
    app.state.auth_rate_limiter = RateLimiter(
        settings.auth_rate_limit, new_window_store()
    )
    app.state.login_throttle = LoginThrottle(_lockout_policy(settings), throttle_store)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    install_security(app, settings, new_window_store)
    if settings.trusted_proxies:
        # Outermost, so rate limits and logs see the real client address.
        app.add_middleware(
            ProxyHeadersMiddleware, trusted_hosts=settings.trusted_proxies
        )
    _include_routers(app, prefix)
    return app


def _lockout_policy(settings: Settings) -> LockoutPolicy:
    """Translate login lockout settings into a throttle policy."""
    return LockoutPolicy(
        free_failures=settings.login_free_failures,
        base_lock_seconds=settings.login_base_lock_seconds,
        max_lock_seconds=settings.login_max_lock_seconds,
        ip_failures=settings.login_ip_failures,
        ip_window_seconds=settings.login_ip_window_seconds,
    )


def _include_routers(app: FastAPI, prefix: str) -> None:
    """Mount every route module under `prefix` (empty, or e.g. "/api")."""
    app.include_router(health.router, prefix=prefix)
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix=f"{prefix}/auth",
        tags=["auth"],
        dependencies=[Depends(enforce_auth_rate_limit)],
    )
    app.include_router(auth_routes.web_router, prefix=prefix)
    app.include_router(auth_routes.mobile_router, prefix=prefix)
    # Before the fastapi-users router, whose `/users/{id}` would claim "me".
    app.include_router(auth_routes.account_router, prefix=prefix)
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix=f"{prefix}/users",
        tags=["users"],
    )
    for router in (
        goals.router,
        tasks.router,
        steps.router,
        postponements.router,
        routines.router,
        plans.router,
        notifications.router,
        onboarding.router,
    ):
        app.include_router(router, prefix=prefix)
