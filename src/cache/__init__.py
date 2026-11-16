"""SecureDoc AI v4 — Cache layer.

A single :class:`CacheBackend` interface, three implementations:

* :class:`MemoryCache` — in-process TTL + LRU, optional AES-GCM encryption.
  Default when Redis is disabled. Per-replica (no sharing).
* :class:`RedisCache` — distributed, shares state across replicas. Enabled
  via ``REDIS_ENABLED=true``. Uses the same encryption as memory.
* :class:`NullCache` — no-op. Returned when ``CACHE_ENABLED=false`` so
  callers never need to check whether caching is on.

Dependency direction
--------------------
- ``src.cache`` may import from ``src.core`` (config, logging, exceptions),
  ``src.security.crypto`` (AES-GCM), and ``src.observability.metrics``.
- ``src.cache`` MUST NOT import from ``api/`` or ``src.rag``.

Public API
----------
>>> from src.cache import get_cache, make_cache_key
>>> cache = await get_cache()
>>> await cache.set("k", "v")
>>> await cache.get("k")
'v'
"""

from __future__ import annotations

from src.cache.base import CacheBackend, NullCache, make_cache_key
from src.cache.factory import get_cache, healthcheck, reset
from src.cache.memory import MemoryCache
from src.cache.redis_cache import RedisCache

__all__ = [
    "CacheBackend",
    "NullCache",
    "MemoryCache",
    "RedisCache",
    "make_cache_key",
    "get_cache",
    "reset",
    "healthcheck",
]
