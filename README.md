# SecureDoc AI: Guardrailed Enterprise RAG Infrastructure

## Overview

SecureDoc AI is a Retrieval-Augmented Generation (RAG) pipeline designed for enterprise environments where data leakage and model hallucination are unacceptable. The system implements semantic boundary chunking, hybrid retrieval (dense + lexical), cross-encoder re-ranking, and strict input/output validation using NeMo Guardrails.

## Project Structure

```
secure-doc-ai/
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
├── Dockerfile.api
├── documents/
│   └── company_policy.txt
├── config/
│   ├── config.yml
│   └── rails/
│       ├── input.co
│       └── output.co
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── logger.py
│   ├── ingest.py
│   ├── hybrid_retriever.py
│   ├── rag_pipeline.py
│   ├── evaluate.py
│   └── utils.py
├── api/
│   ├── __init__.py
│   ├── main.py
│   ├── schemas.py
│   └── middleware.py
├── cli/
│   ├── __init__.py
│   └── main.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_ingest.py
│   ├── test_retriever.py
│   ├── test_pipeline.py
│   └── test_api.py
├── scripts/
│   ├── setup.sh
│   ├── build_index.sh
│   └── run_eval.sh
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── docker-build.yml
├── vectorstore/
│   └── .gitkeep
├── docstore/
│   └── .gitkeep
└── logs/
    └── .gitkeep
```

## Tech Stack

- **Framework:** FastAPI
- **RAG:** LlamaIndex, LangChain
- **Vector Store:** Qdrant
- **Evaluation:** RAGAS
- **Security:** NVIDIA NeMo Guardrails
- **Testing:** pytest

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your API keys

# 2. Install dependencies
make install

# 3. Start services
make up

# 4. Build the index
make build-index

# 5. Run the API
make run-api

# 6. Run the CLI
make run-cli

# 7. Run tests
make test
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `install` | Install production and dev dependencies |
| `lint` | Run ruff and black |
| `test` | Run the pytest suite |
| `up` | Start Docker services |
| `down` | Stop Docker services |
| `build-index` | Build the vector index from documents |
| `run-api` | Start the FastAPI server |
| `run-cli` | Start the CLI interface |
| `run-eval` | Run RAGAS evaluation |
| `format` | Format code with black |
| `clean` | Remove caches and build artifacts |

## License

MIT License
