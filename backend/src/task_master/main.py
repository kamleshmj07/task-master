"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from task_master.config import Settings, get_settings
from task_master.routes import health


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app with middleware and routes."""
    settings = settings or get_settings()
    is_production = settings.environment == "production"
    app = FastAPI(
        title=settings.app_name,
        docs_url=None if is_production else "/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(health.router)
    return app
