"""Health, readiness, deps, metrics."""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from api.schemas import DepsResponse, HealthResponse
from src.config import get_settings
from src.health_check import aggregate

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    s = get_settings()
    return HealthResponse(status="ok", version=s.app_version, environment=s.environment)


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def ready() -> dict[str, str]:
    s = get_settings()
    ok = (s.vectorstore_path / "index.faiss").exists() and s.config_path.exists()
    return {"status": "ready" if ok else "not_ready"}


@router.get("/health/deps", response_model=DepsResponse)
async def deps() -> DepsResponse:
    return DepsResponse(**aggregate())


@router.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
