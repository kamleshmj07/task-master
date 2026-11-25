"""Health checks: is the API up, and can it reach its database?"""

import logging
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from task_master.dependencies import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check payload."""

    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    """Readiness payload: "unavailable" when the database cannot be reached."""

    status: Literal["ok", "unavailable"]


@router.get("/health")
async def get_health() -> HealthResponse:
    """Report that the API is up (without touching the database)."""
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def get_readiness(session: SessionDep, response: Response) -> ReadinessResponse:
    """Report whether the API can serve requests: 503 if the database is down.

    Point uptime checks here, so a broken database is noticed.
    """
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError, OSError:
        logger.error("Readiness check failed: database unreachable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="unavailable")
    return ReadinessResponse(status="ok")
