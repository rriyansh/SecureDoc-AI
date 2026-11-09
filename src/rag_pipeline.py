"""RAG pipeline orchestrating ingest, retrieve, and generate."""

import time
import uuid
from typing import List, Optional

from src.config import config
from src.logger import get_logger
from src.metrics import metrics
from src.audit import get_audit_logger, AuditEventType, AuditLevel
from src.hybrid_retriever import HybridRetriever, RetrievalResult
from src.query_rewriter import query_rewriter, RewrittenQuery
from src.cache import query_cache
from src.security import sanitize_input, detect_pii, redact_pii

logger = get_logger(__name__)


class SecureRAGPipeline:
    def __init__(self):
        self.retriever = HybridRetriever()
        self.audit = get_audit_logger()

    def retrieve(self, query: str) -> List[RetrievalResult]:
        return self.retriever.retrieve(query)

    def query(
        self,
        question: str,
        user_id: str = "anonymous",
        request_id: str = None,
        ip_address: str = None,
        use_cache: bool = True,
        use_rewrite: bool = True,
    ) -> str:
        """Answer a question through the RAG pipeline with full security and observability."""
        request_id = request_id or uuid.uuid4().hex[:12]
        start_time = time.time()

        # Sanitize input
        sanitized_question = sanitize_input(question)

        # Check for PII
        pii_findings = detect_pii(sanitized_question)
        pii_detected = len(pii_findings) > 0
        if pii_detected:
            logger.warning("PII detected in query: %d findings", len(pii_findings))
            sanitized_question = redact_pii(sanitized_question)
            self.audit.log_pii(
                user_id=user_id,
                pii_types=[f["type"] for f in pii_findings],
                request_id=request_id,
                ip_address=ip_address,
            )

        # Check cache
        if use_cache:
            cached = query_cache.get(sanitized_question)
            if cached:
                logger.info("Cache hit for query")
                metrics.record_cache_hit("query")
                self._log_query(user_id, sanitized_question, cached, 0, request_id, ip_address, pii_detected, 0)
                return cached
            metrics.record_cache_miss("query")

        # Rewrite query for better retrieval
        rewritten_queries = [sanitized_question]
        if use_rewrite:
            rewritten = query_rewriter.rewrite_for_retrieval(sanitized_question)
            rewritten_queries = rewritten
            logger.debug("Query rewritten into %d variations", len(rewritten_queries))

        # Retrieve for each rewritten query and combine
        all_results = []
        for q in rewritten_queries:
            results = self.retrieve(q)
            all_results.extend(results)

        # Deduplicate and rerank
        seen = set()
        unique_results = []
        for r in all_results:
            text_hash = hash(r.text[:100])
            if text_hash not in seen:
                seen.add(text_hash)
                unique_results.append(r)

        # Limit to top_k
        final_results = unique_results[:config.top_k]

        retrieval_time = time.time()

        # Generate answer
        answer = self._generate(sanitized_question, final_results)

        generation_time = time.time()

        # Cache the result
        if use_cache and answer:
            query_cache.set(sanitized_question, answer)

        # Log and metrics
        total_duration = generation_time - start_time
        retrieval_duration = retrieval_time - start_time
        generation_duration = generation_time - retrieval_time

        self._log_query(
            user_id=user_id,
            question=sanitized_question,
            answer=answer,
            num_results=len(final_results),
            request_id=request_id,
            ip_address=ip_address,
            pii_detected=pii_detected,
            duration_ms=total_duration * 1000,
        )

        metrics.record_rag_query(
            status="success",
            duration=total_duration,
            retrieval_duration=retrieval_duration,
            generation_duration=generation_duration,
            num_results=len(final_results),
            context_length=sum(len(r.text) for r in final_results),
        )

        logger.info("Query processed in %.1fms (retrieval: %.1fms, generation: %.1fms)",
                    total_duration * 1000, retrieval_duration * 1000, generation_duration * 1000)

        return answer

    def _generate(self, question: str, results: List[RetrievalResult]) -> str:
        """Generate answer using LLM (placeholder)."""
        if not results:
            return "I could not find relevant information in the documents."

        context = "\n\n".join(r.text for r in results)

        # Placeholder for actual LLM call
        # In production, this would call OpenAI or another LLM
        answer = (
            f"Based on the retrieved context:\n{context}\n\n"
            f"Answer to '{question}': (LLM generation placeholder)"
        )
        return answer

    def _log_query(
        self,
        user_id: str,
        question: str,
        answer: str,
        num_results: int,
        request_id: str,
        ip_address: str = None,
        pii_detected: bool = False,
        duration_ms: float = 0,
    ) -> None:
        """Log query to audit trail."""
        self.audit.log_query(
            user_id=user_id,
            question=question,
            answer=answer,
            num_results=num_results,
            duration_ms=duration_ms,
            request_id=request_id,
            ip_address=ip_address,
            pii_detected=pii_detected,
        )