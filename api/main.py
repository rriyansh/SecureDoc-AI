"""FastAPI application entry point."""

import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from api.routes import query, health, admin
from api.middleware import SecurityMiddleware, RateLimitMiddleware, RequestIDMiddleware
from api.schemas import QueryRequest, QueryResponse
from src.rag_pipeline import SecureRAGPipeline
from src.metrics import metrics
from src.logger import get_logger
from src.config import config

logger = get_logger(__name__)

pipeline = SecureRAGPipeline()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting SecureDoc AI API")
    # Startup: initialize connections, warm caches, etc.
    yield
    # Shutdown: cleanup
    logger.info("Shutting down SecureDoc AI API")


app = FastAPI(
    title="SecureDoc AI",
    version="0.1.0",
    description="Guardrailed Enterprise RAG Infrastructure",
    lifespan=lifespan,
    docs_url="/docs" if config.get("app.env") != "production" else None,
    redoc_url="/redoc" if config.get("app.env") != "production" else None,
)

# Add middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityMiddleware)
app.add_middleware(RateLimitMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.get("cors.origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(health.router)
app.include_router(query.router)
app.include_router(admin.router)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": getattr(request.state, "request_id", None)},
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "SecureDoc AI",
        "version": "0.1.0",
        "description": "Guardrailed Enterprise RAG Infrastructure",
        "docs": "/docs",
        "health": "/v1/health",
    }