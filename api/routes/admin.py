"""Admin endpoints (protected by X-Admin-Key)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import get_admin
from api.schemas import StatsResponse
from src.cache import get_response_cache
from src.circuit_breaker import get_llm_breaker
from src.dedup import get_deduplicator
from src.hybrid_retriever import reset_retriever_cache
from src.rag_pipeline import reset_rag_chain_cache
from src.rate_limiter import get_limiter

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/stats", response_model=StatsResponse)
async def stats(_: str = Depends(get_admin)) -> StatsResponse:
    return StatsResponse(
        cache=get_response_cache().stats(),
        rate_limiter=get_limiter().stats(),
        circuit_breaker=get_llm_breaker().stats(),
        dedup=get_deduplicator().stats(),
    )


@router.post("/cache/clear")
async def clear_cache(_: str = Depends(get_admin)) -> dict[str, str]:
    get_response_cache().clear()
    return {"status": "cleared"}


@router.post("/reload")
async def reload_chain(_: str = Depends(get_admin)) -> dict[str, str]:
    reset_retriever_cache()
    reset_rag_chain_cache()
    return {"status": "reloaded"}
