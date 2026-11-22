"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from task_master.auth import routes as auth_routes
from task_master.auth.lockout import LockoutPolicy, LoginThrottle
from task_master.auth.rate_limit import RateLimiter, enforce_auth_rate_limit
from task_master.auth.schemas import UserCreate, UserRead, UserUpdate
from task_master.auth.users import fastapi_users
from task_master.config import Settings, get_settings
from task_master.database import create_engine, create_session_factory
from task_master.routes import (
    goals,
    health,
    plans,
    postponements,
    routines,
    steps,
    tasks,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app with middleware and routes."""
    settings = settings or get_settings()
    engine = create_engine(settings.database_url.get_secret_value())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        await engine.dispose()

    is_production = settings.environment == "production"
    app = FastAPI(
        title=settings.app_name,
        docs_url=None if is_production else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_factory = create_session_factory(engine)
    app.state.auth_rate_limiter = RateLimiter(settings.auth_rate_limit)
    app.state.login_throttle = LoginThrottle(_lockout_policy(settings))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    _include_routers(app)
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


def _include_routers(app: FastAPI) -> None:
    """Mount every route module."""
    app.include_router(health.router)
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
        dependencies=[Depends(enforce_auth_rate_limit)],
    )
    app.include_router(auth_routes.web_router)
    app.include_router(auth_routes.mobile_router)
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )
    app.include_router(goals.router)
    app.include_router(tasks.router)
    app.include_router(steps.router)
    app.include_router(postponements.router)
    app.include_router(routines.router)
    app.include_router(plans.router)
