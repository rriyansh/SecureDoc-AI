"""Prometheus metrics — every counter, histogram, gauge the app emits.

Design rules
------------
1. **Declared once, imported everywhere.** No metric is instantiated outside
   this module. Call sites do ``CACHE_HITS.inc()`` — never
   ``Counter("cache_hits", ...)``.
2. **Low-cardinality labels only.** No user IDs, no request IDs, no free-text.
   Every label value must come from a bounded set (endpoint paths, reasons,
   HTTP methods, status codes).
3. **Unit suffixes** — ``_seconds`` for histograms, ``_total`` for counters.
   Matches Prometheus best practices.
4. **Naming prefix** — every metric is ``securedoc_*`` so dashboards can
   namespace-filter cleanly.

Metric inventory
----------------
HTTP layer:       REQUESTS_TOTAL, QUERY_LATENCY
Cache:            CACHE_HITS, CACHE_MISSES
Rate limiter:     RATE_LIMIT_HITS
Circuit breaker:  CIRCUIT_OPEN (label: name)
Dedup:            DEDUP_HITS
Anomaly:          ANOMALY_HITS (label: kind)
Guardrails:       GUARDRAIL_BLOCKS (label: reason)
PII:              PII_REDACTIONS (label: type)
RAG:              RETRIEVAL_DOCS, RETRIEVAL_LATENCY, INDEX_DOCS, LLM_LATENCY
Fallback:         LLM_FALLBACK
DB:               DB_QUERY_DURATION (label: operation)
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram


# --------------------------------------------------------------------------- #
# HTTP layer                                                                   #
# --------------------------------------------------------------------------- #

REQUESTS_TOTAL = Counter(
    "securedoc_requests_total",
    "Total HTTP requests handled, partitioned by endpoint/method/status.",
    labelnames=["endpoint", "method", "status"],
)

QUERY_LATENCY = Histogram(
    "securedoc_query_latency_seconds",
    "End-to-end latency of POST /api/v1/query (seconds).",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)


# --------------------------------------------------------------------------- #
# Cache                                                                        #
# --------------------------------------------------------------------------- #

CACHE_HITS = Counter(
    "securedoc_cache_hits_total",
    "Number of cache lookups that returned a value.",
)

CACHE_MISSES = Counter(
    "securedoc_cache_misses_total",
    "Number of cache lookups that returned None (miss or expired).",
)


# --------------------------------------------------------------------------- #
# Rate limiting                                                                #
# --------------------------------------------------------------------------- #

RATE_LIMIT_HITS = Counter(
    "securedoc_rate_limit_hits_total",
    "Number of requests rejected by the rate limiter.",
)


# --------------------------------------------------------------------------- #
# Circuit breaker                                                              #
# --------------------------------------------------------------------------- #

CIRCUIT_OPEN = Counter(
    "securedoc_circuit_open_total",
    "Number of times a circuit breaker transitioned to OPEN.",
    labelnames=["name"],
)


# --------------------------------------------------------------------------- #
# Deduplication                                                                #
# --------------------------------------------------------------------------- #

DEDUP_HITS = Counter(
    "securedoc_dedup_hits_total",
    "Number of duplicate requests detected within the dedup window.",
)


# --------------------------------------------------------------------------- #
# Anomaly detection                                                            #
# --------------------------------------------------------------------------- #

ANOMALY_HITS = Counter(
    "securedoc_anomaly_hits_total",
    "Number of anomaly detections (rapid-fire, repeated, or high-entropy).",
    labelnames=["kind"],
)


# --------------------------------------------------------------------------- #
# Guardrails                                                                   #
# --------------------------------------------------------------------------- #

GUARDRAIL_BLOCKS = Counter(
    "securedoc_guardrail_blocks_total",
    "Number of requests blocked by guardrails, partitioned by reason.",
    labelnames=["reason"],
)


# --------------------------------------------------------------------------- #
# PII                                                                          #
# --------------------------------------------------------------------------- #

PII_REDACTIONS = Counter(
    "securedoc_pii_redactions_total",
    "Number of PII redactions performed, partitioned by PII type.",
    labelnames=["type"],
)


# --------------------------------------------------------------------------- #
# RAG pipeline                                                                 #
# --------------------------------------------------------------------------- #

RETRIEVAL_DOCS = Histogram(
    "securedoc_retrieval_docs_returned",
    "Number of documents returned by the retriever before reranking.",
    buckets=(1, 2, 4, 6, 8, 10, 20, 50, 100),
)

RETRIEVAL_LATENCY = Histogram(
    "securedoc_retrieval_latency_seconds",
    "Time spent in retrieval + reranking (seconds).",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

LLM_LATENCY = Histogram(
    "securedoc_llm_latency_seconds",
    "Time spent waiting on the LLM (seconds).",
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60),
)

LLM_FALLBACK = Counter(
    "securedoc_llm_fallback_total",
    "Number of times the fallback LLM was invoked (primary failed).",
)

INDEX_DOCS = Gauge(
    "securedoc_indexed_documents",
    "Number of source documents currently indexed (set on ingest).",
)


# --------------------------------------------------------------------------- #
# Database                                                                     #
# --------------------------------------------------------------------------- #

DB_QUERY_DURATION = Histogram(
    "securedoc_db_query_duration_seconds",
    "Database query duration (seconds), partitioned by operation.",
    labelnames=["operation"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5),
)
