"""Hybrid retrieval: dense vector search + lexical BM25 with cross-encoder re-ranking."""

from typing import List

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class RetrievalResult:
    def __init__(self, text: str, score: float, source: str = ""):
        self.text = text
        self.score = score
        self.source = source


class HybridRetriever:
    def __init__(self, top_k: int = None):
        self.top_k = top_k or config.top_k

    def dense_search(self, query: str) -> List[RetrievalResult]:
        """Placeholder for dense vector search (Qdrant)."""
        logger.debug("Dense search for: %s", query)
        return []

    def lexical_search(self, query: str) -> List[RetrievalResult]:
        """Placeholder for lexical BM25 search."""
        logger.debug("Lexical search for: %s", query)
        return []

    def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Placeholder for cross-encoder re-ranking."""
        return sorted(results, key=lambda r: r.score, reverse=True)[: self.top_k]

    def retrieve(self, query: str) -> List[RetrievalResult]:
        """Execute hybrid retrieval and return re-ranked results."""
        dense = self.dense_search(query)
        lexical = self.lexical_search(query)
        combined = dense + lexical
        return self.rerank(query, combined)
