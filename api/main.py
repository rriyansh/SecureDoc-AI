"""FastAPI application with lifespan management."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import RequestContextMiddleware
from api.routes import admin, health, query
from src.config import get_settings
from src.logger import get_logger

log = get_logger("api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Starting {settings.app_name} v{settings.app_version}")
    try:
        from src.rag_pipeline import build_rag_chain
        build_rag_chain()
        log.success("RAG chain warm-started.")
    except Exception as exc:
        log.error(f"Warm-start failed: {exc}")
    yield
    log.info("Shutting down.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Hardened enterprise RAG with guardrails, auth, caching, and metrics.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    max_age=600,
)
app.add_middleware(RequestContextMiddleware)

app.include_router(health.router)
app.include_router(query.router)
app.include_router(admin.router)
