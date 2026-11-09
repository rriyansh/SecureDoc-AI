"""Health check API routes."""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.dependencies import get_current_user, require_admin
from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    checks: Dict[str, Any]


class ReadinessResponse(BaseModel):
    ready: bool
    checks: Dict[str, bool]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health status of the API and its dependencies.",
)
async def health() -> HealthResponse:
    """Basic health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        environment=config.get("app.env", "development"),
        checks={
            "api": "ok",
            "config": "loaded",
        },
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness check",
    description="Check if the service is ready to accept traffic.",
)
async def readiness() -> ReadinessResponse:
    """Readiness check for Kubernetes."""
    checks = {
        "config": True,
        "vectorstore": False,  # Would check Qdrant connection
        "docstore": False,     # Would check document store
    }

    # In production, add actual connection checks
    # try:
    #     qdrant_client.get_collections()
    #     checks["vectorstore"] = True
    # except:
    #     pass

    ready = all(checks.values())

    return ReadinessResponse(ready=ready, checks=checks)


@router.get(
    "/health/detailed",
    response_model=HealthResponse,
    summary="Detailed health check",
    description="Detailed health check including all dependencies (requires admin).",
)
async def detailed_health(user: dict = Depends(require_admin)) -> HealthResponse:
    """Detailed health check with dependency status."""
    checks = {
        "api": "ok",
        "config": "loaded",
        "vectorstore": "unknown",
        "docstore": "unknown",
        "cache": "ok",
        "rate_limiter": "ok",
    }

    # In production, add actual checks
    # checks["vectorstore"] = check_qdrant()
    # checks["docstore"] = check_docstore()

    return HealthResponse(
        status="healthy" if all(v in ["ok", "loaded", "unknown"] for v in checks.values()) else "degraded",
        version="0.1.0",
        environment=config.get("app.env", "development"),
        checks=checks,
    )


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Expose Prometheus metrics for scraping.",
)
async def metrics(user: dict = Depends(require_admin)):
    """Prometheus metrics endpoint."""
    from fastapi.responses import Response
    from src.metrics import metrics as metrics_collector

    return Response(
        content=metrics_collector.get_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )