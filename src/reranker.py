"""Cross-encoder reranker with graceful degradation."""

from __future__ import annotations

from functools import lru_cache

from src.config import get_settings
from src.logger import get_logger

log = get_logger("reranker")


@lru_cache(maxsize=1)
def _load_model():
    try:
        from sentence_transformers import CrossEncoder
        m = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
        log.info("Cross-encoder loaded.")
        return m
    except Exception as exc:  # pragma: no cover
        log.warning(f"Reranker unavailable: {exc}")
        return None


def rerank(query: str, docs: list, top_k: int | None = None) -> list:
    s = get_settings()
    top_k = top_k or s.rerank_top_k
    if not docs or not s.enable_reranker:
        return docs[:top_k]
    model = _load_model()
    if model is None:
        return docs[:top_k]
    try:
        pairs = [(query, getattr(d, "page_content", str(d))) for d in docs]
        scores = model.predict(pairs)
        return [d for _, d in sorted(zip(scores, docs, strict=False), key=lambda x: -x[0])][:top_k]
    except Exception as exc:  # pragma: no cover
        log.warning(f"Rerank failed: {exc}")
        return docs[:top_k]
