#  SecureDoc AI

Enterprise-grade **Retrieval-Augmented Generation (RAG)** system with hybrid search, guardrails, and automated evaluation.

##  Features

- **Parent-Child Chunking** — Semantic retrieval with full-context generation
- **Hybrid Search** — BM25 (keyword) + Vector (semantic) fusion for superior recall
- **NeMo Guardrails** — Prompt injection prevention + grounded output rails
- **RAGAS Evaluation** — Faithfulness, context precision & recall tracking
- **Streaming API** — Server-Sent Events for low-latency token streaming
- **Production Ready** — Docker, CI/CD, type hints, structured logging, tests

##  Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Documents      │────▶│  Ingest          │────▶│  Vectorstore     │
│  (.txt/.pdf)    │     │  Parent-Child    │     │  (FAISS)         │
└─────────────────┘     │  Chunking        │     │  + Docstore      │
                        └──────────────────┘     └──────────────────┘
                                                          │
┌─────────────────┐     ┌──────────────────┐              │
│  User Query     │────▶│  Hybrid Retriever│◀─────────────┘
└─────────────────┘     │  BM25 + Vector   │
                        └──────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │  NeMo Guardrails │  ← Input rails (injection)
                        └──────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │  LLM + RAG Chain │
                        └──────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │  Output Rails    │  ← Grounding + PII
                        └──────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │  Streaming API   │  ← SSE / REST
                        └──────────────────┘
```

## Quick Start

### Option A: Docker (Recommended)

```bash
git clone <repo-url> securedoc-ai && cd securedoc-ai
cp .env.example .env  # Add your OPENAI_API_KEY
docker compose up --build
```

The API will be live at `http://localhost:8000/docs`.

### Option B: Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env  # Add your OPENAI_API_KEY
make ingest   # Build vector indexes
make run      # Start the API
```

## API Usage

### Streaming Query

```bash
curl -N -X POST http://localhost:8000/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "How long is customer data retained?"}'
```

### Standard Query

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Who can access customer data?"}'
```

### Health Check

```bash
curl http://localhost:8000/health
```

##  Make Commands

| Command | Description |
|---------|-------------|
| `make install` | Install dependencies |
| `make ingest` | Build vector indexes |
| `make run` | Start API server |
| `make cli` | Interactive CLI |
| `make eval` | Run RAGAS evaluation |
| `make test` | Run test suite |
| `make lint` | Run linters |
| `make format` | Format code |
| `make clean` | Remove artifacts |
| `make docker` | Build Docker image |

## Testing

```bash
make test          # Full test suite
make test-fast     # Without coverage
pytest tests/test_api.py -v   # Single file
```

##  Evaluation

RAGAS metrics are computed over a curated test set:

```bash
make eval
```

Output:
```
faithfulness:          0.92
answer_relevancy:      0.89
context_precision:     0.87
context_recall:        0.95
```

## Security

- **Input rails** block prompt injection & jailbreak attempts
- **Output rails** enforce grounding and PII redaction
- **No secrets in code** — `.env` pattern enforced
- **Non-root Docker user** — container runs as `appuser`

## Project Structure

```
src/     — Core RAG logic (ingest, retriever, pipeline, eval)
api/     — FastAPI application with streaming endpoints
cli/     — Interactive command-line interface
config/  — NeMo Guardrails (Colang flows + YAML)
tests/   — Pytest test suite
scripts/ — Setup, build, and evaluation shell scripts
```

##  Contributing

1. Fork the repo
2. Create a feature branch
3. Run `make lint && make test`
4. Open a Pull Request

## 📄 License

MIT — see [LICENSE](LICENSE).
