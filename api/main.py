"""FastAPI application with lifespan and layered middlewares."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import error_handlers
from api.middleware import RequestContextMiddleware
from api.routes import admin, health, query
from api.routes import openapi as openapi_ext
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
    description="Advanced enterprise RAG with guardrails, auth, crypto, and observability.",
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

error_handlers.register(app)
openapi_ext.register(app)
