"""SecureDoc AI v4 — Observability layer.

Two concerns:

* :mod:`src.observability.metrics` — Prometheus counters, histograms, and
  gauges. Every metric the application emits is declared here exactly once,
  so the ``/metrics`` endpoint exposes a stable, documented schema.
* :mod:`src.observability.health` — aggregate dependency probes for
  ``/health/deps``. Combines DB, cache, vectorstore, and config checks.

Dependency direction
--------------------
- ``src.observability`` may import from ``src.core`` and the top-level
  packages whose health it probes (``src.db.session``, ``src.cache.factory``).
- It MUST NOT be imported BY ``src.core`` (would create a cycle).

Public API
----------
>>> from src.observability.metrics import CACHE_HITS, QUERY_LATENCY
>>> from src.observability.health import aggregate
"""

from __future__ import annotations

from src.observability.health import aggregate, check_cache, check_config, check_db, check_vectorstore
from src.observability.metrics import (
    ANOMALY_HITS,
    CACHE_HITS,
    CACHE_MISSES,
    CIRCUIT_OPEN,
    DB_QUERY_DURATION,
    DEDUP_HITS,
    GUARDRAIL_BLOCKS,
    INDEX_DOCS,
    LLM_FALLBACK,
    LLM_LATENCY,
    PII_REDACTIONS,
    QUERY_LATENCY,
    RATE_LIMIT_HITS,
    REQUESTS_TOTAL,
    RETRIEVAL_DOCS,
    RETRIEVAL_LATENCY,
)

__all__ = [
    # Metrics
    "REQUESTS_TOTAL",
    "QUERY_LATENCY",
    "CACHE_HITS",
    "CACHE_MISSES",
    "RATE_LIMIT_HITS",
    "GUARDRAIL_BLOCKS",
    "RETRIEVAL_DOCS",
    "RETRIEVAL_LATENCY",
    "INDEX_DOCS",
    "PII_REDACTIONS",
    "CIRCUIT_OPEN",
    "DEDUP_HITS",
    "ANOMALY_HITS",
    "LLM_FALLBACK",
    "LLM_LATENCY",
    "DB_QUERY_DURATION",
    # Health
    "aggregate",
    "check_db",
    "check_cache",
    "check_vectorstore",
    "check_config",
]
