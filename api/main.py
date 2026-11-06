"""FastAPI application entry point."""

from __future__ import annotations

import json
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from api.middleware import RequestContextMiddleware
from api.schemas import HealthResponse, QueryRequest, QueryResponse
from src.config import get_settings
from src.logger import get_logger
from src.rag_pipeline import build_rag_chain

log = get_logger("api")
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Enterprise RAG with hybrid search, guardrails, and streaming.",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)


@app.on_event("startup")
async def _startup() -> None:
    log.info(f"Starting {settings.app_name} v{settings.app_version}")
    try:
        build_rag_chain()
        log.success("RAG chain warm-started.")
    except Exception as exc:  # pragma: no cover
        log.error(f"RAG chain warm-start failed: {exc}")


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
    )


@app.post("/query", response_model=QueryResponse, tags=["rag"])
async def query(request: QueryRequest) -> QueryResponse:
    start = time.perf_counter()
    try:
        chain = build_rag_chain()
        answer = chain.invoke(request.question)
    except Exception as exc:
        log.exception("RAG pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    latency_ms = (time.perf_counter() - start) * 1000
    return QueryResponse(
        question=request.question, answer=answer, latency_ms=round(latency_ms, 2)
    )


async def _stream_generator(question: str):
    yield {"event": "status", "data": json.dumps({"stage": "retrieving"})}
    try:
        chain = build_rag_chain()
        async for chunk in chain.astream(question):
            if chunk:
                yield {"event": "token", "data": json.dumps({"text": chunk})}
        yield {"event": "done", "data": json.dumps({"status": "complete"})}
    except Exception as exc:
        log.exception("Streaming failed")
        yield {"event": "error", "data": json.dumps({"error": str(exc)})}


@app.post("/query/stream", tags=["rag"])
async def query_stream(request: QueryRequest) -> EventSourceResponse:
    return EventSourceResponse(_stream_generator(request.question))
