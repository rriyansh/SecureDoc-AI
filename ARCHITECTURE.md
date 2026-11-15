# SecureDoc AI Architecture

## Overview

SecureDoc AI is a guardrailed enterprise RAG (Retrieval-Augmented Generation) infrastructure designed for secure document processing and querying.

## System Components

### Core Layer (`src/core/`)
- **config.py**: Centralized configuration management
- **context.py**: Request context and correlation IDs
- **exceptions.py**: Custom exception hierarchy
- **logger.py**: Structured logging setup

### Database Layer (`src/db/`)
- **base.py**: SQLAlchemy declarative base
- **session.py**: Database session management
- **models.py**: ORM models
- **repositories/**: Data access layer

### Security Layer (`src/security/`)
- **auth.py**: Authentication (API keys, JWT)
- **crypto.py**: Encryption utilities
- **pii.py**: PII detection and redaction
- **request_signer.py**: Request signing/verification
- **sanitize.py**: Input sanitization

### Cache Layer (`src/cache/`)
- **base.py**: Cache interface
- **factory.py**: Cache backend factory
- **memory.py**: In-memory cache implementation
- **redis_cache.py**: Redis cache implementation

### Resilience Layer (`src/resilience/`)
- **circuit_breaker.py**: Circuit breaker pattern
- **rate_limiter.py**: Token bucket rate limiting
- **dedup.py**: Request deduplication
- **anomaly.py**: Anomaly detection

### Observability (`src/observability/`)
- **metrics.py**: Prometheus metrics
- **health.py**: Health check endpoints

### RAG Pipeline (`src/rag/`)
- **ingest.py**: Document ingestion
- **pipeline.py**: RAG orchestration
- **retriever.py**: Hybrid retrieval (dense + lexical)
- **reranker.py**: Cross-encoder reranking
- **query_rewriter.py**: Query expansion

## API Layer (`api/`)
- **main.py**: FastAPI application
- **routes/**: API route modules
- **schemas.py**: Pydantic models
- **dependencies.py**: Dependency injection
- **middleware.py**: Custom middleware
- **error_handlers.py**: Exception handlers

## Web UI (`web/`)
- Static assets and Jinja2 templates for admin interface

## CLI (`cli/`)
- Command-line interface for administration

## Data Flow

1. Documents → Ingest → Chunk → Embed → Vector Store
2. Query → Rewrite → Retrieve → Rerank → Generate → Response
3. All paths guarded by security rails (NeMo Guardrails)

## Security Model

- Zero-trust architecture
- All inputs sanitized and validated
- PII detection and redaction
- Audit logging for all operations
- Rate limiting and circuit breaking