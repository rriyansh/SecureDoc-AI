"""RAG query endpoints (standard + streaming)."""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from api.dependencies import rate_limited
from api.schemas import QueryRequest, QueryResponse
from src.audit import record as audit
from src.cache import cache_key, get_response_cache
from src.config import get_settings
from src.logger import get_logger
from src.metrics import GUARDRAIL_BLOCKS, QUERY_LATENCY
from src.rag_pipeline import build_rag_chain, safe_query
from src.security import scan

log = get_logger("api.query")
router = APIRouter(prefix="/api/v1", tags=["rag"])


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest, principal: str = Depends(rate_limited)
) -> QueryResponse:
    start = time.perf_counter()
    s = get_settings()

    pre = scan(request.question)
    if not pre.clean:
        GUARDRAIL_BLOCKS.labels(reason="input_scan").inc()
        audit("query_blocked", principal=principal, question=request.question)
        raise HTTPException(status_code=400, detail="Request blocked by input safety check")

    cache = get_response_cache() if s.cache_enabled else None
    ck = cache_key(principal, request.question)

    if cache:
        cached = cache.get(ck)
        if cached is not None:
            latency = (time.perf_counter() - start) * 1000
            QUERY_LATENCY.observe(latency / 1000)
            audit("query_cache_hit", principal=principal, question=request.question)
            return QueryResponse(
                question=request.question, answer=cached,
                latency_ms=round(latency, 2), cached=True,
            )

    try:
        chain = build_rag_chain()
        answer = safe_query(chain, request.question)
    except Exception as exc:
        log.exception("RAG failed")
        audit("query_error", principal=principal, error=str(exc))
        raise HTTPException(status_code=500, detail="Pipeline failure") from exc

    if cache:
        cache.set(ck, answer)

    latency = (time.perf_counter() - start) * 1000
    QUERY_LATENCY.observe(latency / 1000)
    audit("query", principal=principal, question=request.question, latency_ms=latency)
    return QueryResponse(question=request.question, answer=answer, latency_ms=round(latency, 2))


async def _stream(question: str, principal: str):
    yield {"event": "status", "data": json.dumps({"stage": "scanning"})}
    pre = scan(question)
    if not pre.clean:
        GUARDRAIL_BLOCKS.labels(reason="input_scan").inc()
        audit("query_blocked", principal=principal, question=question)
        yield {"event": "error", "data": json.dumps({"error": "blocked"})}
        return

    yield {"event": "status", "data": json.dumps({"stage": "generating"})}
    try:
        chain = build_rag_chain()
        try:
            async for chunk in chain.astream(pre.redacted_text):
                if chunk:
                    yield {"event": "token", "data": json.dumps({"text": chunk})}
        except (NotImplementedError, TypeError):
            result = chain.invoke(pre.redacted_text)
            yield {"event": "token", "data": json.dumps({"text": result})}

        yield {"event": "done", "data": json.dumps({"status": "complete"})}
        audit("query_stream", principal=principal, question=question)
    except Exception as exc:
        log.exception("Stream failed")
        yield {"event": "error", "data": json.dumps({"error": str(exc)})}


@router.post("/query/stream")
async def query_stream(
    request: QueryRequest, principal: str = Depends(rate_limited)
) -> EventSourceResponse:
    return EventSourceResponse(_stream(request.question, principal))
