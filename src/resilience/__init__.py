"""SecureDoc AI v4 — Resilience layer.

Four independent resilience primitives, each with a single job:

* :mod:`circuit_breaker` — CLOSED/OPEN/HALF_OPEN state machine for
  protecting downstream calls (LLM, embeddings). Prevents cascading failure.
* :mod:`rate_limiter` — token-bucket or sliding-window limiter per principal.
* :mod:`dedup` — window-based deduplication of in-flight requests.
* :mod:`anomaly` — lightweight behavioral detection (rapid-fire, repeated,
  high-entropy payloads). Detection only — never blocks requests.

Dependency direction
--------------------
- ``src.resilience`` may import from ``src.core`` and
  ``src.observability.metrics``.
- ``src.resilience`` MUST NOT import from ``api/`` or ``src.rag``.

Public API
----------
>>> from src.resilience import get_llm_breaker, get_limiter, get_deduplicator
>>> breaker = get_llm_breaker()
>>> limiter = get_limiter()
>>> dedup = get_deduplicator()
"""

from __future__ import annotations

from src.resilience.anomaly import AnomalyDetector, check_anomaly, get_detector
from src.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    get_llm_breaker,
)
from src.resilience.dedup import Deduplicator, get_deduplicator
from src.resilience.rate_limiter import (
    SlidingWindowLimiter,
    TokenBucketLimiter,
    get_limiter,
)

__all__ = [
    # Circuit breaker
    "CircuitBreaker",
    "CircuitState",
    "get_llm_breaker",
    # Rate limiter
    "TokenBucketLimiter",
    "SlidingWindowLimiter",
    "get_limiter",
    # Dedup
    "Deduplicator",
    "get_deduplicator",
    # Anomaly
    "AnomalyDetector",
    "get_detector",
    "check_anomaly",
]
