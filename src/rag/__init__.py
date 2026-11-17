"""SecureDoc AI v4 — RAG pipeline.

Complete Retrieval-Augmented Generation stack:

* :mod:`ingest` — document loading, parent-child chunking, FAISS indexing
* :mod:`query_rewriter` — normalization + abbreviation/synonym expansion
* :mod:`retriever` — hybrid BM25 + FAISS retrieval
* :mod:`reranker` — cross-encoder rerank with graceful degradation
* :mod:`pipeline` — guarded RAG (NeMo rails + circuit breaker + fallback LLM)
* :mod:`evaluate` — RAGAS offline evaluation

Dependency direction
--------------------
- ``src.rag`` may import from ``src.core``, ``src.security``,
  ``src.resilience``, ``src.observability``.
- ``src.rag`` MUST NOT import from ``api/``.

Public API
----------
>>> from src.rag.pipeline import build_rag_chain, safe_query
>>> from src.rag.retriever import retrieve_and_rerank
>>> from src.rag.ingest import ingest
"""

from __future__ import annotations

from src.rag.ingest import ingest
from src.rag.pipeline import (
    build_fallback_llm,
    build_rag_chain,
    reset_cache as reset_pipeline_cache,
    safe_query,
)
from src.rag.query_rewriter import rewrite
from src.rag.reranker import rerank
from src.rag.retriever import (
    build_hybrid_retriever,
    reset_cache as reset_retriever_cache,
    retrieve_and_rerank,
)

__all__ = [
    # Ingest
    "ingest",
    # Pipeline
    "build_rag_chain",
    "build_fallback_llm",
    "safe_query",
    "reset_pipeline_cache",
    # Query rewriting
    "rewrite",
    # Retriever
    "build_hybrid_retriever",
    "retrieve_and_rerank",
    "reset_retriever_cache",
    # Reranker
    "rerank",
]
