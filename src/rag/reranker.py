"""Cross-encoder reranking.

Why rerank
----------
Hybrid retrieval (BM25 + dense) is fast but approximate. A cross-encoder
reads (query, document) **together** and scores their relevance with much
higher accuracy — but it can't be used to index millions of docs because
it's O(N) per query.

Two-stage architecture:

1. **Retrieve** — hybrid returns top-K (default 10) candidates cheaply.
2. **Rerank** — cross-encoder scores each candidate precisely, return top-N
   (default 4).

Model choice
------------
``cross-encoder/ms-marco-MiniLM-L-6-v2`` — ~80 MB, ~1 ms per pair on CPU,
MS MARCO trained (well-calibrated for general IR).

Graceful degradation
--------------------
* Model weights unavailable → log once, return input order.
* ``sentence-transformers`` not installed → same.
* Config ``ENABLE_RERANKER=false`` → skip entirely.
* Prediction error on a batch → return input order, log warning.

This means **ingest still works without the reranker dependency**, and
deployments can choose not to install it.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from src.core.config import get_settings
from src.core.logger import get_logger

log = get_logger("rag.reranker")

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_BATCH_SIZE = 16


@lru_cache(maxsize=1)
def _load_model() -> Any | None:
    """Load the cross-encoder once. Returns None if unavailable."""
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        log.warning(
            "sentence-transformers not installed — reranker disabled. "
            "Install with: pip install sentence-transformers"
        )
        return None

    try:
        model = CrossEncoder(_MODEL_NAME, max_length=512)
        log.info(f"Cross-encoder loaded: {_MODEL_NAME}")
        return model
    except Exception as exc:
        log.warning(f"Failed to load reranker ({_MODEL_NAME}): {exc}")
        return None


def _doc_text(doc: Any) -> str:
    """Extract text from a LangChain Document or plain string."""
    if hasattr(doc, "page_content"):
        return doc.page_content
    return str(doc)


def rerank(
    query: str,
    docs: list[Any],
    *,
    top_k: int | None = None,
) -> list[Any]:
    """Rerank documents by cross-encoder score.

    Parameters
    ----------
    query : str
        The (possibly rewritten) user query.
    docs : list
        Candidate documents from the retriever.
    top_k : int | None
        Number to return. Defaults to ``settings.rerank_top_k``.

    Returns
    -------
    list
        Top-``top_k`` documents by descending relevance. Falls back to the
        input order (truncated to ``top_k``) if reranking is unavailable.
    """
    s = get_settings()
    k = top_k if top_k is not None else s.rerank_top_k

    if not docs:
        return []

    if k < 1:
        raise ValueError("top_k must be >= 1")

    # Fast path: reranker disabled by config
    if not s.enable_reranker:
        return docs[:k]

    # Fast path: only one candidate — nothing to rerank
    if len(docs) == 1:
        return docs[:1]

    model = _load_model()
    if model is None:
        # Reranker unavailable — return first k in retrieval order
        return docs[:k]

    try:
        pairs = [(query, _doc_text(doc)) for doc in docs]
        scores = model.predict(
            pairs,
            batch_size=_BATCH_SIZE,
            show_progress_bar=False,
        )
    except Exception as exc:
        log.warning(f"Reranker prediction failed, falling back: {exc}")
        return docs[:k]

    # Sort by score descending, preserve original doc objects
    ranked = [
        doc for _, doc in sorted(
            zip(scores, docs, strict=False), key=lambda x: -float(x[0])
        )
    ]

    log.debug(f"Reranked {len(docs)} → top {k}")
    return ranked[:k]
