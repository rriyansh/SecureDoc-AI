"""Prometheus metrics for monitoring."""

import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from functools import wraps

from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry, generate_latest
from prometheus_client.core import REGISTRY

from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MetricsCollector:
    """Centralized metrics collector."""

    registry: CollectorRegistry = field(default_factory=CollectorRegistry)

    # Request metrics
    http_requests_total: Counter = field(init=False)
    http_request_duration_seconds: Histogram = field(init=False)
    http_request_size_bytes: Histogram = field(init=False)
    http_response_size_bytes: Histogram = field(init=False)

    # RAG pipeline metrics
    rag_queries_total: Counter = field(init=False)
    rag_query_duration_seconds: Histogram = field(init=False)
    rag_retrieval_duration_seconds: Histogram = field(init=False)
    rag_generation_duration_seconds: Histogram = field(init=False)
    rag_retrieval_results: Histogram = field(init=False)
    rag_context_length: Histogram = field(init=False)

    # Retrieval metrics
    retrieval_dense_duration_seconds: Histogram = field(init=False)
    retrieval_lexical_duration_seconds: Histogram = field(init=False)
    retrieval_rerank_duration_seconds: Histogram = field(init=False)
    retrieval_total_results: Histogram = field(init=False)

    # Cache metrics
    cache_hits_total: Counter = field(init=False)
    cache_misses_total: Counter = field(init=False)
    cache_size: Gauge = field(init=False)

    # Rate limiter metrics
    rate_limit_exceeded_total: Counter = field(init=False)
    rate_limit_remaining: Gauge = field(init=False)

    # Auth metrics
    auth_success_total: Counter = field(init=False)
    auth_failure_total: Counter = field(init=False)

    # Security metrics
    pii_detected_total: Counter = field(init=False)
    input_sanitized_total: Counter = field(init=False)

    # Ingestion metrics
    documents_ingested_total: Counter = field(init=False)
    chunks_created_total: Counter = field(init=False)
    ingestion_duration_seconds: Histogram = field(init=False)

    # Evaluation metrics
    evaluation_runs_total: Counter = field(init=False)
    evaluation_metrics: Gauge = field(init=False)

    # System metrics
    active_connections: Gauge = field(init=False)
    memory_usage_bytes: Gauge = field(init=False)

    def __post_init__(self):
        self._init_metrics()

    def _init_metrics(self):
        """Initialize all Prometheus metrics."""
        # HTTP metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
            registry=self.registry,
        )
        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry,
        )
        self.http_request_size_bytes = Histogram(
            "http_request_size_bytes",
            "HTTP request size in bytes",
            ["method", "endpoint"],
            registry=self.registry,
        )
        self.http_response_size_bytes = Histogram(
            "http_response_size_bytes",
            "HTTP response size in bytes",
            ["method", "endpoint"],
            registry=self.registry,
        )

        # RAG metrics
        self.rag_queries_total = Counter(
            "rag_queries_total",
            "Total RAG queries",
            ["status"],
            registry=self.registry,
        )
        self.rag_query_duration_seconds = Histogram(
            "rag_query_duration_seconds",
            "RAG query total duration",
            ["status"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry,
        )
        self.rag_retrieval_duration_seconds = Histogram(
            "rag_retrieval_duration_seconds",
            "RAG retrieval duration",
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
            registry=self.registry,
        )
        self.rag_generation_duration_seconds = Histogram(
            "rag_generation_duration_seconds",
            "RAG generation duration",
            buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry,
        )
        self.rag_retrieval_results = Histogram(
            "rag_retrieval_results",
            "Number of retrieval results",
            buckets=[0, 1, 2, 3, 4, 5, 10, 20, 50],
            registry=self.registry,
        )
        self.rag_context_length = Histogram(
            "rag_context_length",
            "Length of context passed to LLM",
            buckets=[100, 500, 1000, 2000, 4000, 8000, 16000, 32000],
            registry=self.registry,
        )

        # Retrieval metrics
        self.retrieval_dense_duration_seconds = Histogram(
            "retrieval_dense_duration_seconds",
            "Dense vector search duration",
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry,
        )
        self.retrieval_lexical_duration_seconds = Histogram(
            "retrieval_lexical_duration_seconds",
            "Lexical BM25 search duration",
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry,
        )
        self.retrieval_rerank_duration_seconds = Histogram(
            "retrieval_rerank_duration_seconds",
            "Cross-encoder rerank duration",
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
            registry=self.registry,
        )
        self.retrieval_total_results = Histogram(
            "retrieval_total_results",
            "Total results before reranking",
            buckets=[0, 5, 10, 25, 50, 100, 200, 500],
            registry=self.registry,
        )

        # Cache metrics
        self.cache_hits_total = Counter(
            "cache_hits_total",
            "Total cache hits",
            ["cache_type"],
            registry=self.registry,
        )
        self.cache_misses_total = Counter(
            "cache_misses_total",
            "Total cache misses",
            ["cache_type"],
            registry=self.registry,
        )
        self.cache_size = Gauge(
            "cache_size",
            "Current cache size",
            ["cache_type"],
            registry=self.registry,
        )

        # Rate limiter metrics
        self.rate_limit_exceeded_total = Counter(
            "rate_limit_exceeded_total",
            "Total rate limit exceeded events",
            ["scope", "key"],
            registry=self.registry,
        )
        self.rate_limit_remaining = Gauge(
            "rate_limit_remaining",
            "Remaining rate limit tokens",
            ["scope", "key"],
            registry=self.registry,
        )

        # Auth metrics
        self.auth_success_total = Counter(
            "auth_success_total",
            "Total successful authentications",
            ["method"],
            registry=self.registry,
        )
        self.auth_failure_total = Counter(
            "auth_failure_total",
            "Total failed authentications",
            ["method", "reason"],
            registry=self.registry,
        )

        # Security metrics
        self.pii_detected_total = Counter(
            "pii_detected_total",
            "Total PII detections",
            ["pii_type"],
            registry=self.registry,
        )
        self.input_sanitized_total = Counter(
            "input_sanitized_total",
            "Total inputs sanitized",
            registry=self.registry,
        )

        # Ingestion metrics
        self.documents_ingested_total = Counter(
            "documents_ingested_total",
            "Total documents ingested",
            registry=self.registry,
        )
        self.chunks_created_total = Counter(
            "chunks_created_total",
            "Total chunks created",
            registry=self.registry,
        )
        self.ingestion_duration_seconds = Histogram(
            "ingestion_duration_seconds",
            "Document ingestion duration",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry,
        )

        # Evaluation metrics
        self.evaluation_runs_total = Counter(
            "evaluation_runs_total",
            "Total evaluation runs",
            ["status"],
            registry=self.registry,
        )
        self.evaluation_metrics = Gauge(
            "evaluation_metric",
            "Evaluation metric value",
            ["metric_name"],
            registry=self.registry,
        )

        # System metrics
        self.active_connections = Gauge(
            "active_connections",
            "Number of active connections",
            registry=self.registry,
        )
        self.memory_usage_bytes = Gauge(
            "memory_usage_bytes",
            "Memory usage in bytes",
            registry=self.registry,
        )

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float,
        request_size: int = 0,
        response_size: int = 0,
    ):
        """Record HTTP request metrics."""
        self.http_requests_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        self.http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        if request_size:
            self.http_request_size_bytes.labels(method=method, endpoint=endpoint).observe(request_size)
        if response_size:
            self.http_response_size_bytes.labels(method=method, endpoint=endpoint).observe(response_size)

    def record_rag_query(self, status: str, duration: float, retrieval_duration: float = 0, generation_duration: float = 0, num_results: int = 0, context_length: int = 0):
        """Record RAG query metrics."""
        self.rag_queries_total.labels(status=status).inc()
        self.rag_query_duration_seconds.labels(status=status).observe(duration)
        if retrieval_duration:
            self.rag_retrieval_duration_seconds.observe(retrieval_duration)
        if generation_duration:
            self.rag_generation_duration_seconds.observe(generation_duration)
        if num_results:
            self.rag_retrieval_results.observe(num_results)
        if context_length:
            self.rag_context_length.observe(context_length)

    def record_retrieval(self, dense_duration: float = 0, lexical_duration: float = 0, rerank_duration: float = 0, total_results: int = 0):
        """Record retrieval metrics."""
        if dense_duration:
            self.retrieval_dense_duration_seconds.observe(dense_duration)
        if lexical_duration:
            self.retrieval_lexical_duration_seconds.observe(lexical_duration)
        if rerank_duration:
            self.retrieval_rerank_duration_seconds.observe(rerank_duration)
        if total_results:
            self.retrieval_total_results.observe(total_results)

    def record_cache_hit(self, cache_type: str):
        """Record cache hit."""
        self.cache_hits_total.labels(cache_type=cache_type).inc()

    def record_cache_miss(self, cache_type: str):
        """Record cache miss."""
        self.cache_misses_total.labels(cache_type=cache_type).inc()

    def update_cache_size(self, cache_type: str, size: int):
        """Update cache size gauge."""
        self.cache_size.labels(cache_type=cache_type).set(size)

    def record_rate_limit_exceeded(self, scope: str, key: str):
        """Record rate limit exceeded."""
        self.rate_limit_exceeded_total.labels(scope=scope, key=key[:8]).inc()

    def update_rate_limit_remaining(self, scope: str, key: str, remaining: float):
        """Update rate limit remaining."""
        self.rate_limit_remaining.labels(scope=scope, key=key[:8]).set(remaining)

    def record_auth_success(self, method: str):
        """Record auth success."""
        self.auth_success_total.labels(method=method).inc()

    def record_auth_failure(self, method: str, reason: str):
        """Record auth failure."""
        self.auth_failure_total.labels(method=method, reason=reason).inc()

    def record_pii_detected(self, pii_type: str):
        """Record PII detection."""
        self.pii_detected_total.labels(pii_type=pii_type).inc()

    def record_input_sanitized(self):
        """Record input sanitization."""
        self.input_sanitized_total.inc()

    def record_ingestion(self, num_documents: int, num_chunks: int, duration: float):
        """Record ingestion metrics."""
        self.documents_ingested_total.inc(num_documents)
        self.chunks_created_total.inc(num_chunks)
        self.ingestion_duration_seconds.observe(duration)

    def record_evaluation(self, status: str, metrics: Dict[str, float]):
        """Record evaluation metrics."""
        self.evaluation_runs_total.labels(status=status).inc()
        for name, value in metrics.items():
            self.evaluation_metrics.labels(metric_name=name).set(value)

    def set_active_connections(self, count: int):
        """Set active connections."""
        self.active_connections.set(count)

    def set_memory_usage(self, bytes_used: int):
        """Set memory usage."""
        self.memory_usage_bytes.set(bytes_used)

    def get_metrics(self) -> bytes:
        """Get Prometheus metrics in text format."""
        return generate_latest(self.registry)


metrics = MetricsCollector()


def track_duration(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to track function duration."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                logger.debug("%s took %.3fs", metric_name, duration)
        return wrapper
    return decorator