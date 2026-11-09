#  SecureDoc AI v2

Enterprise-grade Retrieval-Augmented Generation (RAG) system for secure document querying with hybrid search, guardrails, authentication, caching, reranking, and automated evaluation.

---

##  Features

- Hybrid Search — BM25 + FAISS semantic fusion
- Parent-Child Chunking — Full-context retrieval
- NeMo Guardrails — Prompt injection & PII protection
- JWT + API-Key Auth — bcrypt-hashed secrets
- Token Bucket Rate Limiting — Per-principal
- TTL + LRU Response Cache — Configurable
- Cross-Encoder Reranking — Graceful fallback
- Query Rewriting — Abbreviation expansion + synonyms
- PII Detection & Redaction — Input + output
- JSONL Audit Trail — Per-request logging
- Prometheus Metrics — `/metrics` endpoint
- Streaming SSE API — Low-latency token streaming
- RAGAS Evaluation — Faithfulness, precision, recall
- Docker + CI/CD — Production-ready deployment

---

##  Architecture

Documents → Ingest (Parent-Child) → Vectorstore (FAISS + Docstore)
User Query → Hybrid Retriever (BM25 + Vector + Rerank)
NeMo Input Rails (injection check) → LLM + RAG Chain
Output Rails (grounding + PII) → Streaming API (SSE / REST)

---

## 📁 Project Structure

securedoc-ai/
├── .env.example
├── .gitignore
├── .dockerignore
├── .pre-commit-config.yaml
├── LICENSE
├── README.md
├── Makefile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── docker-compose.yml
├── Dockerfile
├── documents/company_policy.txt
├── config/
│   ├── config.yml
│   └── rails/{input.co, output.co, retrieval.co}
├── src/
│   ├── __init__.py, config.py, logger.py, utils.py
│   ├── security.py, auth.py, rate_limiter.py, cache.py
│   ├── metrics.py, audit.py, query_rewriter.py, reranker.py
│   ├── ingest.py, hybrid_retriever.py, rag_pipeline.py, evaluate.py
├── api/
│   ├── __init__.py, main.py, schemas.py
│   ├── middleware.py, dependencies.py
│   └── routes/{__init__.py, query.py, health.py, admin.py}
├── cli/{__init__.py, main.py}
├── tests/
│   ├── conftest.py, test_utils.py, test_retriever.py
│   ├── test_pipeline.py, test_api.py, test_security.py
│   ├── test_auth.py, test_rate_limiter.py, test_cache.py
├── scripts/
│   ├── setup.sh, build_index.sh, run_eval.sh
│   ├── rotate_keys.sh, healthcheck.sh
├── .github/workflows/{ci.yml, docker-build.yml, security-scan.yml}
├── vectorstore/.gitkeep
├── docstore/.gitkeep
├── audit/.gitkeep
└── logs/.gitkeep

---

##  Prerequisites

- Python 3.10+
- OpenAI API key
- (Optional) Docker + Docker Compose
- 4GB+ RAM for cross-encoder reranker

---

##  Quick Start

Step 1: Clone / create project
git clone <repo-url> securedoc-ai && cd securedoc-ai

Step 2: Setup virtualenv + dependencies
bash scripts/setup.sh
chmod +x scripts/*.sh

Step 3: Generate strong keys
bash scripts/rotate_keys.sh
Copy output into .env

Step 4: Configure
Edit .env → set OPENAI_API_KEY, API_KEYS, JWT_SECRET, ADMIN_API_KEY

Step 5: Activate
source .venv/bin/activate

Step 6: Ingest documents
make ingest

Step 7: Verify
make test
make lint

Step 8: Run
make run

API live at: http://localhost:8000
Docs: http://localhost:8000/docs
Metrics: http://localhost:8000/metrics

---

##  Required Environment Variables (.env)

Required:
OPENAI_API_KEY=sk-your-key-here
API_KEYS=<hex-32>,<hex-32>
JWT_SECRET=<hex-32-at-least-32-chars>
ADMIN_API_KEY=<hex-32>

Optional (defaults shown):
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
ENVIRONMENT=production
LOG_LEVEL=INFO
CACHE_ENABLED=true
ENABLE_RERANKER=true
ENABLE_QUERY_REWRITE=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=10

Full template → .env.example

---

##  API Endpoints

GET  /health                    → Basic health (no auth)
GET  /health/live               → Liveness probe (no auth)
GET  /health/ready              → Readiness probe (no auth)
GET  /metrics                   → Prometheus metrics (no auth)
POST /api/v1/query              → RAG query (API-Key / JWT)
POST /api/v1/query/stream       → SSE stream (API-Key / JWT)
GET  /api/v1/admin/stats        → Cache & limiter stats (Admin-Key)
POST /api/v1/admin/cache/clear  → Clear cache (Admin-Key)
POST /api/v1/admin/reload       → Reload chain (Admin-Key)

Example — Standard query:
curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: $YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "How long is customer data retained?"}'

Example — Streaming query:
curl -N -X POST http://localhost:8000/api/v1/query/stream \
  -H "X-API-Key: $YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Who can access customer data?"}'

---

##  Make Commands

make setup        → Create venv + install + create .env
make install      → Install dependencies
make ingest       → Build vector index
make run          → Start FastAPI (dev mode)
make cli          → Interactive CLI
make eval         → RAGAS evaluation
make test         → Full test suite with coverage
make test-fast    → Tests without coverage
make lint         → ruff + mypy + bandit
make format       → Auto-format code
make clean        → Remove caches and artifacts
make docker       → Build Docker image
make docker-up    → Start docker compose
make docker-down  → Stop docker compose
make rotate-keys  → Generate fresh keys
make health       → curl health endpoints

---

## Testing

make test                        → full suite + coverage
make test-fast                   → faster (no coverage)
pytest tests/test_api.py -v      → single file
make lint                        → ruff + mypy + bandit

---

## 📊 Evaluation

make eval
Output: evaluation_results.json
Metrics: faithfulness, answer_relevancy, context_precision, context_recall

---

##  Docker Deployment

Build:
docker build -t securedoc-ai:2.0.0 .

Run via compose:
docker compose up --build -d

Logs:
docker compose logs -f securedoc-api

Stop:
docker compose down

Security: non-root user, cap_drop ALL, read-only tmpfs, resource limits, healthcheck.

---

## Security Layers

1. Auth — API key / JWT / Admin key (bcrypt-hashed)
2. Rate Limiting — Token bucket per principal
3. Input Sanitization — Control chars stripped, length clamped
4. Prompt Injection Detection — Regex heuristics + NeMo rails
5. PII Detection & Redaction — Email, SSN, credit card, Aadhaar, PAN, IP, phone
6. NeMo Guardrails — Input + output + retrieval rails
7. Output Grounding — Refuses ungrounded answers
8. Response Cache — TTL + LRU per principal
9. Audit Trail — JSONL per-request logging
10. Security Headers — HSTS, CSP, XFO, XCTO, Referrer-Policy
11. Body Size Guard — 413 on oversize payloads

---

## Metrics (Prometheus)

securedoc_requests_total              → Requests by endpoint/method/status
securedoc_query_latency_seconds       → End-to-end query latency
securedoc_cache_hits_total            → Cache hits
securedoc_cache_misses_total          → Cache misses
securedoc_rate_limit_hits_total       → Rate-limit violations
securedoc_guardrail_blocks_total      → Guardrail blocks by reason
securedoc_retrieval_docs_returned     → Docs returned histogram
securedoc_indexed_documents           → Indexed docs gauge
securedoc_pii_redactions_total        → PII redactions by type

---

## Tech Stack

Orchestration     → LangChain (LCEL)
Guardrails        → NVIDIA NeMo Guardrails + Colang
Vector Store      → FAISS (cpu)
Keyword Search    → rank-bm25
Reranker          → sentence-transformers (CrossEncoder)
LLM / Embeddings  → OpenAI (gpt-4o-mini, text-embedding-3-small)
API               → FastAPI + Uvicorn + sse-starlette
Auth              → python-jose (JWT) + passlib (bcrypt)
Metrics           → prometheus-client
Logging           → loguru
Config            → pydantic-settings
Evaluation        → RAGAS
Testing           → pytest + pytest-asyncio + httpx
Lint / Types      → ruff + mypy + bandit
Container         → Docker + Compose

---

##  Workflow Summary

1. Ingest — Documents → Parent-Child chunks → FAISS index + docstore
2. Query — User question → Sanitize → Cache check → Query rewrite
3. Retrieve — Hybrid search (BM25 + Vector) → Cross-encoder rerank
4. Guard — NeMo input rails → LLM → NeMo output rails
5. Redact — PII detection on output
6. Respond — Cache + audit + metrics
7. Evaluate — RAGAS periodically

---

##  Troubleshooting

FAISS index not found       → Run make ingest first
401 Unauthorized            → Check X-API-Key header matches API_KEYS
429 Too Many Requests       → Increase RATE_LIMIT_PER_MINUTE or wait
Reranker unavailable        → Install sentence-transformers or set ENABLE_RERANKER=false
NeMo import error           → pip install nemoguardrails
Slow ingestion              → Reduce PARENT_CHUNK_SIZE or batch documents

---

## 📄 License

MIT — see LICENSE.

---

##  Contributing

1. Fork the repo
2. Create a feature branch
3. Run make lint && make test
4. Open a Pull Request

---

Built with ❤️ for secure enterprise RAG.
