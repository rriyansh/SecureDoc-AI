"""Hybrid retrieval: dense vector search + lexical BM25 with cross-encoder re-ranking."""

import time
from typing import List, Optional

from src.config import config
from src.logger import get_logger
from src.metrics import metrics
from src.reranker import reranker, RerankResult

logger = get_logger(__name__)


class RetrievalResult:
    def __init__(self, text: str, score: float, source: str = "", metadata: dict = None):
        self.text = text
        self.score = score
        self.source = source
        self.metadata = metadata or {}


class HybridRetriever:
    def __init__(self, top_k: int = None):
        self.top_k = top_k or config.top_k
        self.rerank_top_k = config.rerank_top_k
        self.hybrid_alpha = config.hybrid_alpha

    def dense_search(self, query: str) -> List[RetrievalResult]:
        """Placeholder for dense vector search (Qdrant)."""
        start = time.time()
        logger.debug("Dense search for: %s", query)
        # In production, this would query Qdrant
        results = []
        duration = time.time() - start
        metrics.record_retrieval(dense_duration=duration)
        return results

    def lexical_search(self, query: str) -> List[RetrievalResult]:
        """Placeholder for lexical BM25 search."""
        start = time.time()
        logger.debug("Lexical search for: %s", query)
        # In production, this would query a BM25 index
        results = []
        duration = time.time() - start
        metrics.record_retrieval(lexical_duration=duration)
        return results

    def combine_results(
        self,
        dense: List[RetrievalResult],
        lexical: List[RetrievalResult],
    ) -> List[RetrievalResult]:
        """Combine dense and lexical results using reciprocal rank fusion."""
        # Simple combination for now - in production use RRF
        combined = dense + lexical

        # Deduplicate by text
        seen = set()
        unique = []
        for result in combined:
            text_hash = hash(result.text[:100])
            if text_hash not in seen:
                seen.add(text_hash)
                unique.append(result)

        return unique

    def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Rerank using cross-encoder."""
        if not results:
            return []

        start = time.time()
        # Convert to format expected by reranker
        rerank_results = reranker.rerank(query, results, top_k=self.rerank_top_k)

        # Convert back to RetrievalResult
        final_results = []
        for rr in rerank_results[:self.top_k]:
            final_results.append(RetrievalResult(
                text=rr.text,
                score=rr.score,
                source=rr.source,
            ))

        duration = time.time() - start
        metrics.record_retrieval(rerank_duration=duration)
        return final_results

    def retrieve(self, query: str) -> List[RetrievalResult]:
        """Execute hybrid retrieval and return re-ranked results."""
        start = time.time()

        dense = self.dense_search(query)
        lexical = self.lexical_search(query)
        combined = self.combine_results(dense, lexical)

        logger.debug("Combined %d dense + %d lexical = %d unique results", len(dense), len(lexical), len(combined))

        if not combined:
            duration = time.time() - start
            metrics.record_retrieval(total_results=0)
            return []

        reranked = self.rerank(query, combined)

        total_duration = time.time() - start
        metrics.record_retrieval(total_results=len(reranked))

        logger.info("Retrieved %d results for query in %.3fs", len(reranked), total_duration)
        return reranked