"""Prometheus metrics."""

from prometheus_client import Counter, Gauge, Histogram

REQUESTS_TOTAL = Counter(
    "securedoc_requests_total", "Total HTTP requests",
    ["endpoint", "method", "status"],
)
QUERY_LATENCY = Histogram(
    "securedoc_query_latency_seconds", "Query latency",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)
CACHE_HITS = Counter("securedoc_cache_hits_total", "Cache hits")
CACHE_MISSES = Counter("securedoc_cache_misses_total", "Cache misses")
RATE_LIMIT_HITS = Counter("securedoc_rate_limit_hits_total", "Rate-limit violations")
GUARDRAIL_BLOCKS = Counter(
    "securedoc_guardrail_blocks_total", "Guardrail blocks", ["reason"]
)
RETRIEVAL_DOCS = Histogram(
    "securedoc_retrieval_docs_returned", "Docs returned",
    buckets=(1, 2, 4, 6, 8, 10, 20, 50),
)
INDEX_DOCS = Gauge("securedoc_indexed_documents", "Indexed documents")
PII_REDACTIONS = Counter(
    "securedoc_pii_redactions_total", "PII redactions", ["type"]
)
