"""Hybrid BM25 + FAISS retriever.

Two-stage retrieval
-------------------
1. **Hybrid recall** — BM25 (lexical) + FAISS (semantic), fused via
   :class:`EnsembleRetriever`. Weights come from config (default 0.4/0.6).
   Lexical search catches exact terms ("Aadhaar"), semantic catches
   paraphrases ("12-digit government ID").

2. **Rerank** — cross-encoder re-scores top-K to top-N (see
   :mod:`src.rag.reranker`).

Caching
-------
The :class:`EnsembleRetriever` is a singleton via ``lru_cache`` — building
it requires loading BM25 corpus and opening the FAISS index. Building per
request would be 50-200ms of wasted work.

Re-ingest
---------
After running ``python -m src.rag.ingest`` in a running process, call
:func:`reset_cache` to force the retriever to reload the new index.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from langchain.retrievers import BM25Retriever, EnsembleRetriever
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from src.core.config import get_settings
from src.core.logger import get_logger
from src.observability.metrics import RETRIEVAL_DOCS, RETRIEVAL_LATENCY
from src.rag.reranker import rerank

log = get_logger("rag.retriever")


# --------------------------------------------------------------------------- #
# Internal helpers                                                             #
# --------------------------------------------------------------------------- #

def _load_bm25_corpus(documents_path) -> list:
    """Load raw documents for BM25 indexing.

    BM25 needs the **original** documents (not chunks) — chunking would break
    term-frequency statistics. We load every ``.txt`` in full.
    """
    docs: list = []
    for file in sorted(documents_path.glob("*.txt")):
        docs.extend(TextLoader(str(file), encoding="utf-8").load())
    if not docs:
        raise ValueError(
            f"No .txt files in {documents_path} — run ingest before querying"
        )
    return docs


# --------------------------------------------------------------------------- #
# Retriever builder                                                            #
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=1)
def build_hybrid_retriever() -> EnsembleRetriever:
    """Build and cache the hybrid retriever.

    Raises
    ------
    FileNotFoundError
        If ``vectorstore/index.faiss`` is missing — user must run ingest first.
    """
    s = get_settings()

    index_path = s.vectorstore_path / "index.faiss"
    if not index_path.exists():
        raise FileNotFoundError(
            f"FAISS index missing at {index_path}. "
            f"Run `python -m src.rag.ingest` first."
        )

    # 1. Vector component
    log.info(f"Loading FAISS index from {s.vectorstore_path}")
    embeddings = OpenAIEmbeddings(
        model=s.openai_embedding_model,
        api_key=s.openai_api_key.get_secret_value(),
    )
    vectorstore = FAISS.load_local(
        str(s.vectorstore_path),
        embeddings,
        allow_dangerous_deserialization=True,  # safe — index is local & trusted
    )
    vector_retriever = vectorstore.as_retriever(
        search_kwargs={"k": s.retriever_top_k}
    )

    # 2. BM25 component
    log.info(f"Building BM25 index from {s.documents_path}")
    bm25_corpus = _load_bm25_corpus(s.documents_path)
    bm25_retriever = BM25Retriever.from_documents(bm25_corpus)
    bm25_retriever.k = s.retriever_top_k

    # 3. Ensemble
    ensemble = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[s.bm25_weight, s.vector_weight],
    )
    log.info(
        f"Hybrid retriever ready "
        f"(BM25={s.bm25_weight} Vector={s.vector_weight} k={s.retriever_top_k})"
    )
    return ensemble


# --------------------------------------------------------------------------- #
# Public retrieve+rerank                                                       #
# --------------------------------------------------------------------------- #

def retrieve_and_rerank(query: str) -> list[Any]:
    """Retrieve candidates and rerank them.

    Returns
    -------
    list
        Top ``rerank_top_k`` documents, ranked by cross-encoder (or input
        order if reranker unavailable).

    Metrics
    -------
    * ``RETRIEVAL_DOCS`` — number of candidates returned by hybrid stage.
    * ``RETRIEVAL_LATENCY`` — time from start of retrieve to end of rerank.
    """
    s = get_settings()
    start = time.monotonic()

    retriever = build_hybrid_retriever()
    candidates = retriever.invoke(query)
    RETRIEVAL_DOCS.observe(len(candidates))

    reranked = rerank(query, candidates, top_k=s.rerank_top_k)

    elapsed = time.monotonic() - start
    RETRIEVAL_LATENCY.observe(elapsed)
    log.debug(
        f"Retrieved {len(candidates)} → reranked {len(reranked)} "
        f"in {elapsed * 1000:.1f}ms"
    )
    return reranked


# --------------------------------------------------------------------------- #
# Cache reset                                                                  #
# --------------------------------------------------------------------------- #

def reset_cache() -> None:
    """Clear the singleton retriever — used after re-ingest or in tests."""
    build_hybrid_retriever.cache_clear()
    log.info("Retriever cache reset")
