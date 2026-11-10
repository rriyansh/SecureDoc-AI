

<div align="center">


  # SecureDoc AI v2

  ### Enterprise-Grade RAG System with Guardrails, Hybrid Search & Audit Control

  [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)
  [![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
  [![LangChain](https://img.shields.io/badge/LangChain-LCEL-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://www.langchain.com/)
  [![NeMo Guardrails](https://img.shields.io/badge/NVIDIA-NeMo_Guardrails-76B900?style=flat-square&logo=nvidia&logoColor=white)](https://github.com/NVIDIA/NeMo-Guardrails)
  [![FAISS](https://img.shields.io/badge/FAISS-CPU-00599C?style=flat-square)](https://github.com/facebookresearch/faiss)
  [![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)

  <p align="center">
    <a href="#features">Features</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#tech-stack">Tech Stack</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#api-endpoints">API Reference</a> •
    <a href="#security-layers">Security</a>
  </p>

</div>

---

## Executive Summary

**SecureDoc AI v2** is an enterprise-grade Retrieval-Augmented Generation (RAG) platform engineered for highly secure document querying. Powered by **LangChain**, **NVIDIA NeMo Guardrails**, **FAISS**, and **FastAPI**, it integrates hybrid vector/keyword retrieval, cross-encoder reranking, robust PII redaction, token-bucket rate limiting, and real-time SSE token streaming.

---

## Features

| Category | Capability | Description |
| :--- | :--- | :--- |
| **Retrieval** | Hybrid Search | BM25 + FAISS semantic fusion with parent-child chunking |
| **Optimization** | Reranking & Rewriting | Cross-encoder reranking and synonym/abbreviation query expansion |
| **Safety** | NeMo Guardrails | Input prompt injection detection and output grounding verification |
| **Privacy** | PII Redaction | Automated input/output detection for SSNs, emails, PANs, and IDs |
| **Auth & Security** | Access Control | JWT and bcrypt-hashed API-Key auth with token-bucket rate limiting |
| **Performance** | Response Caching | Configurable TTL + LRU caching layer per principal |
| **Observability** | Audit & Metrics | Per-request JSONL audit trails and Prometheus `/metrics` endpoint |
| **Streaming** | Real-time SSE | Low-latency token streaming support via Server-Sent Events |

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SecureDoc AI Pipeline                            │
│                                                                             │
│   ┌──────────┐    ┌─────────────────────┐    ┌──────────────────────────┐   │
│   │ Documents│───▶│ Parent-Child Chunk  │───▶│ Vectorstore              │   │
│   │          │    │ Ingestion Engine    │    │ (FAISS + Docstore)       │   │
│   └──────────┘    └─────────────────────┘    └────────────┬─────────────┘   │
│                                                           │                 │
│                                                           ▼                 │
│   ┌──────────┐    ┌─────────────────────┐    ┌──────────────────────────┐   │
│   │  User    │───▶│ NeMo Input Rails    │───▶│ Hybrid Retriever         │   │
│   │  Query   │    │ (Injection Check)   │    │ (BM25 + Vector + Rerank) │   │
│   └──────────┘    └─────────────────────┘    └────────────┬─────────────┘   │
│                                                           │                 │
│                                                           ▼                 │
│   ┌──────────┐    ┌─────────────────────┐    ┌──────────────────────────┐   │
│   │ Response │◀───│ Streaming API       │◀───│ NeMo Output Rails        │   │
│   │ Payload  │    │ (SSE / REST)        │    │ (Grounding + PII Filter) │   │
│   └──────────┘    └─────────────────────┘    └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

```

---

## Project Structure

```text
securedoc-ai/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Continuous Integration pipeline
│       ├── docker-build.yml       # Container build workflow
│       └── security-scan.yml      # Vulnerability scanning workflow
├── config/
│   ├── config.yml                 # Global system configuration
│   └── rails/                     # NeMo Guardrails rules (.co / .yml)
│       ├── input.co
│       ├── output.co
│       └── retrieval.co
├── documents/                     # Source documents for ingestion
├── src/                           # Core application package
│   ├── config.py                  # Settings & environment validation
│   ├── logger.py                  # Loguru logging setup
│   ├── security.py                # PII redaction & sanitization
│   ├── auth.py                    # JWT & API Key authentication
│   ├── rate_limiter.py            # Token bucket rate limiting
│   ├── cache.py                   # Response cache (TTL/LRU)
│   ├── metrics.py                 # Prometheus telemetry
│   ├── audit.py                   # JSONL audit logging
│   ├── query_rewriter.py          # Query expansion & synonyms
│   ├── reranker.py                # Cross-Encoder reranking
│   ├── ingest.py                  # Parent-child chunking & FAISS setup
│   ├── hybrid_retriever.py        # Ensemble retriever (BM25 + Vector)
│   ├── rag_pipeline.py            # LCEL RAG chain orchestration
│   └── evaluate.py                # RAGAS evaluation runner
├── api/                           # FastAPI web layer
│   ├── main.py                    # Application factory
│   ├── schemas.py                 # Pydantic request/response models
│   ├── middleware.py             # Security, metrics, & audit middleware
│   ├── dependencies.py           # Dependency injection & auth guards
│   └── routes/                    # API route controllers
│       ├── query.py               # RAG execution & streaming endpoints
│       ├── health.py              # Probes (liveness/readiness)
│       └── admin.py               # Cache & operational admin tools
├── cli/                           # Interactive CLI interface
├── tests/                         # Test suite (unit, API, security)
├── scripts/                       # Maintenance & deployment shell scripts
├── vectorstore/                   # Local FAISS index persistence
├── docstore/                      # Parent document store persistence
├── audit/                         # Audit trail JSONL outputs
├── logs/                          # System execution logs
├── docker-compose.yml             # Local microservice setup
├── Dockerfile                     # Hardened container image build
├── Makefile                       # Development & execution shortcuts
├── pyproject.toml                 # Tool & linters configuration
└── requirements.txt               # Production dependencies

```

---

## Prerequisites

* **Python**: `3.10+`
* **API Key**: OpenAI API credentials
* **Memory**: 4GB+ RAM (required for cross-encoder reranking models)
* **Container Tooling**: Docker & Docker Compose (optional)

---

## Quick Start

### 1. Project Setup

```bash
git clone [https://github.com/your-org/securedoc-ai.git](https://github.com/your-org/securedoc-ai.git)
cd securedoc-ai

bash scripts/setup.sh
chmod +x scripts/*.sh

```

### 2. Secret Key Generation

```bash
bash scripts/rotate_keys.sh

```

*Copy the printed key values directly into your `.env` configuration.*

### 3. Environment Configuration

Create `.env` using `.env.example` as a template and set the required variables:

```env
OPENAI_API_KEY=sk-your-openai-api-key
API_KEYS=your-hex-32-api-key
JWT_SECRET=your-hex-32-jwt-secret-min-32-chars
ADMIN_API_KEY=your-hex-32-admin-key

```

### 4. Indexing & Execution

```bash
# Activate environment
source .venv/bin/activate

# Build document vector index
make ingest

# Execute tests & linting
make test
make lint

# Launch development server
make run

```

> **Live API Base**: `http://localhost:8000` | **OpenAPI Docs**: `http://localhost:8000/docs` | **Metrics**: `http://localhost:8000/metrics`

---

## API Endpoints

### System Endpoints

| Method | Endpoint | Auth Required | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | None | Basic service status check |
| `GET` | `/health/live` | None | Kubernetes liveness probe |
| `GET` | `/health/ready` | None | Kubernetes readiness probe |
| `GET` | `/metrics` | None | Prometheus telemetry scraping |

### RAG & Administrative Endpoints

| Method | Endpoint | Auth Required | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/query` | API-Key / JWT | Standard RAG question-answering |
| `POST` | `/api/v1/query/stream` | API-Key / JWT | Server-Sent Events (SSE) token streaming |
| `GET` | `/api/v1/admin/stats` | Admin-Key | System cache and rate-limiter stats |
| `POST` | `/api/v1/admin/cache/clear` | Admin-Key | Flushes active response cache |
| `POST` | `/api/v1/admin/reload` | Admin-Key | Hot-reloads RAG chain & config |

### Usage Examples

#### Standard Query Execution

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: $YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "How long is customer data retained?"}'

```

#### SSE Streaming Query Execution

```bash
curl -N -X POST http://localhost:8000/api/v1/query/stream \
  -H "X-API-Key: $YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Who can access customer data?"}'

```

---

## Security Layers

1. **Authentication & Authorization**: Multi-principal authentication using JWT (HS256) and bcrypt-hashed API keys.
2. **Rate Limiting**: Token bucket algorithm applied per authenticated principal.
3. **Input Sanitization**: Removal of control characters, structural clamping, and input length capping.
4. **Prompt Injection Guard**: Combination of heuristic regex patterns and NVIDIA NeMo Guardrail policies.
5. **PII Detection & Redaction**: Input/output automated scrubbing for sensitive identity markers.
6. **Grounding Assurance**: Output rails check factual alignment against retrieved contexts to prevent hallucinations.
7. **Response Caching**: Isolated TTL/LRU cache scoping per principal.
8. **Audit Trail**: Structured JSONL audit logging for compliance.
9. **Security Headers**: HSTS, Content-Security-Policy (CSP), X-Frame-Options, and X-Content-Type-Options protection.

---

## Make Command Reference

| Command | Action |
| --- | --- |
| `make setup` | Initialize virtual environment, install dependencies, create `.env` |
| `make install` | Install workspace packages |
| `make ingest` | Parse source documents and generate FAISS vector index |
| `make run` | Launch FastAPI app in development mode with hot reload |
| `make cli` | Start interactive command-line interface |
| `make eval` | Run RAGAS framework pipeline evaluation |
| `make test` | Run complete test suite with coverage report |
| `make test-fast` | Execute tests without coverage computation |
| `make lint` | Run Ruff, MyPy, and Bandit security scans |
| `make format` | Automatically format source code |
| `make clean` | Purge local build artifacts, caches, and temp files |
| `make docker` | Build production Docker image |
| `make docker-up` | Launch local stack using Docker Compose |
| `make docker-down` | Stop running Docker Compose services |
| `make rotate-keys` | Generate fresh cryptographic keys |

---

## Docker Deployment

### Build Container

```bash
docker build -t securedoc-ai:2.0.0 .

```

### Compose Stack Launch

```bash
docker compose up --build -d

```

### Stack Management

```bash
# View active container logs
docker compose logs -f securedoc-api

# Teardown deployment
docker compose down

```

---

## Tech Stack

| Domain | Technology |
| --- | --- |
| **Orchestration** | LangChain (LCEL) |
| **Guardrails** | NVIDIA NeMo Guardrails + Colang |
| **Vector Store** | FAISS (CPU) |
| **Keyword Search** | rank-bm25 |
| **Reranking** | sentence-transformers (CrossEncoder) |
| **LLM / Embeddings** | OpenAI (`gpt-4o-mini`, `text-embedding-3-small`) |
| **API Framework** | FastAPI + Uvicorn + `sse-starlette` |
| **Authentication** | `python-jose` (JWT) + `passlib` (bcrypt) |
| **Metrics & Logs** | `prometheus-client` + Loguru |
| **Evaluation** | RAGAS |
| **Code Hygiene** | Pytest, Ruff, MyPy, Bandit |

---

## Troubleshooting

| Symptom | Cause | Solution |
| --- | --- | --- |
| `FAISS index not found` | Missing vector index | Run `make ingest` before starting API |
| `401 Unauthorized` | Invalid header key | Check that `X-API-Key` matches `.env` settings |
| `429 Too Many Requests` | Rate limit breached | Increase `RATE_LIMIT_PER_MINUTE` or wait |
| `Reranker unavailable` | Missing model package | Install `sentence-transformers` or set `ENABLE_RERANKER=false` |
| `NeMo import error` | Missing guardrails engine | Run `pip install nemoguardrails` |

---

## License

Distributed under the **MIT License**. See [LICENSE](https://www.google.com/search?q=LICENSE) for details.



```

```
