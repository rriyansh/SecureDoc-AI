"""Cross-encoder reranker for improved retrieval relevance."""

import time
from typing import List, Optional, Tuple
from dataclasses import dataclass

import numpy as np

from src.config import config
from src.logger import get_logger
from src.hybrid_retriever import RetrievalResult
from src.metrics import metrics

logger = get_logger(__name__)


@dataclass
class RerankResult:
    """Result of reranking."""
    text: str
    score: float
    source: str
    original_score: float
    rerank_score: float


class CrossEncoderReranker:
    """Cross-encoder based reranker."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        batch_size: int = 32,
        max_length: int = 512,
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name, max_length=self.max_length)
                logger.info("Loaded cross-encoder model: %s", self.model_name)
            except ImportError:
                logger.warning("sentence-transformers not installed, using fallback")
                self._model = "fallback"

    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> List[RerankResult]:
        """Rerank results using cross-encoder."""
        if not results:
            return []

        start_time = time.time()
        top_k = top_k or config.rerank_top_k

        self._load_model()

        if self._model == "fallback":
            return self._fallback_rerank(query, results, top_k)

        try:
            # Prepare pairs for cross-encoder
            pairs = [(query, result.text) for result in results]

            # Get scores in batches
            scores = []
            for i in range(0, len(pairs), self.batch_size):
                batch = pairs[i:i + self.batch_size]
                batch_scores = self._model.predict(batch, show_progress_bar=False)
                scores.extend(batch_scores)

            # Create reranked results
            reranked = []
            for result, score in zip(results, scores):
                reranked.append(RerankResult(
                    text=result.text,
                    score=float(score),
                    source=result.source,
                    original_score=result.score,
                    rerank_score=float(score),
                ))

            # Sort by rerank score descending
            reranked.sort(key=lambda r: r.rerank_score, reverse=True)

            # Record metrics
            duration = time.time() - start_time
            metrics.record_retrieval(rerank_duration=duration)

            logger.debug("Reranked %d results in %.3fs", len(results), duration)
            return reranked[:top_k]

        except Exception as e:
            logger.error("Cross-encoder rerank failed: %s", e)
            return self._fallback_rerank(query, results, top_k)

    def _fallback_rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int,
    ) -> List[RerankResult]:
        """Fallback reranking using simple scoring."""
        query_terms = set(query.lower().split())

        reranked = []
        for result in results:
            # Simple term overlap scoring
            result_terms = set(result.text.lower().split())
            overlap = len(query_terms & result_terms)
            term_score = overlap / max(len(query_terms), 1)

            # Combine with original score
            combined_score = 0.7 * result.score + 0.3 * term_score

            reranked.append(RerankResult(
                text=result.text,
                score=combined_score,
                source=result.source,
                original_score=result.score,
                rerank_score=combined_score,
            ))

        reranked.sort(key=lambda r: r.rerank_score, reverse=True)
        return reranked[:top_k]


class HybridReranker:
    """Hybrid reranker combining multiple signals."""

    def __init__(self):
        self.cross_encoder = CrossEncoderReranker()
        self.weights = {
            "cross_encoder": 0.6,
            "original_score": 0.2,
            "recency": 0.1,
            "source_authority": 0.1,
        }

    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> List[RerankResult]:
        """Rerank using hybrid approach."""
        if not results:
            return []

        top_k = top_k or config.rerank_top_k

        # Get cross-encoder scores
        ce_results = self.cross_encoder.rerank(query, results, top_k=len(results))

        # Get source authority scores (placeholder)
        source_scores = self._get_source_scores(results)

        # Get recency scores (placeholder)
        recency_scores = self._get_recency_scores(results)

        # Combine scores
        final_results = []
        for i, result in enumerate(results):
            ce_score = ce_results[i].rerank_score if i < len(ce_results) else 0.0
            original = result.score
            recency = recency_scores.get(result.source, 0.5)
            authority = source_scores.get(result.source, 0.5)

            combined = (
                self.weights["cross_encoder"] * ce_score +
                self.weights["original_score"] * original +
                self.weights["recency"] * recency +
                self.weights["source_authority"] * authority
            )

            final_results.append(RerankResult(
                text=result.text,
                score=combined,
                source=result.source,
                original_score=original,
                rerank_score=ce_score,
            ))

        final_results.sort(key=lambda r: r.score, reverse=True)
        return final_results[:top_k]

    def _get_source_scores(self, results: List[RetrievalResult]) -> dict:
        """Get authority scores for sources."""
        # Placeholder: in production, load from config or database
        source_authority = {
            "policy": 0.9,
            "regulation": 0.95,
            "standard": 0.85,
            "guideline": 0.8,
            "procedure": 0.75,
        }
        scores = {}
        for result in results:
            source_key = result.source.lower()
            for key, score in source_authority.items():
                if key in source_key:
                    scores[result.source] = score
                    break
            else:
                scores[result.source] = 0.5
        return scores

    def _get_recency_scores(self, results: List[RetrievalResult]) -> dict:
        """Get recency scores for sources."""
        # Placeholder: in production, compute from document metadata
        return {result.source: 0.5 for result in results}


reranker = HybridReranker()