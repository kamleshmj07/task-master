"""Health check endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check payload."""

    status: Literal["ok"]


@router.get("/health")
async def get_health() -> HealthResponse:
    """Report that the API is up."""
    return HealthResponse(status="ok")
