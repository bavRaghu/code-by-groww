"""
Health-check endpoint.

GET /api/v1/health  →  basic liveness probe.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """
    Liveness probe.

    Returns a simple JSON payload confirming the API is reachable.
    Does NOT check database connectivity at this stage.
    """
    from app.config import settings

    return HealthResponse(status="ok", version=settings.app_version)
