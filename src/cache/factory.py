"""Cache factory — singleton with fallback.

Decision tree
-------------
::

    if not CACHE_ENABLED:        → NullCache
    elif REDIS_ENABLED and ping → RedisCache
    elif REDIS_ENABLED but fail → MemoryCache (log warning)
    else                        → MemoryCache

Singleton behavior
------------------
The cache is built **once per process**, lazily on first request. Concurrent
first-requests are serialized via ``asyncio.Lock`` to prevent thundering-herd
Redis connection attempts.

Testing
-------
Call ``await reset()`` between tests to force a rebuild.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.cache.base import CacheBackend, NullCache
from src.cache import memory as memory_cache
from src.core.config import get_settings
from src.core.logger import get_logger

log = get_logger("cache.factory")

_cache: CacheBackend | None = None
_lock = asyncio.Lock()


async def _build() -> CacheBackend:
    """Construct the right cache backend based on settings."""
    s = get_settings()

    if not s.cache_enabled:
        log.info("Cache disabled (CACHE_ENABLED=false) → NullCache")
        return NullCache()

    if s.redis_enabled:
        try:
            from src.cache import redis_cache

            cache = await redis_cache.build()
            log.info("Cache backend selected: redis")
            return cache
        except Exception as exc:
            log.warning(
                f"Redis unavailable ({type(exc).__name__}: {exc}) → "
                f"falling back to memory cache"
            )

    cache = memory_cache.build()
    log.info("Cache backend selected: memory")
    return cache


async def get_cache() -> CacheBackend:
    """Return the process-wide cache, building it on first call."""
    global _cache
    if _cache is not None:
        return _cache
    async with _lock:
        if _cache is not None:
            return _cache
        _cache = await _build()
        return _cache


async def reset() -> None:
    """Close and drop the cached backend — for tests."""
    global _cache
    async with _lock:
        if _cache is not None:
            try:
                await _cache.close()
            except Exception as exc:
                log.warning(f"Cache close failed during reset: {exc}")
        _cache = None


async def healthcheck() -> dict[str, Any]:
    """Aggregate healthcheck used by ``/health/deps``."""
    try:
        cache = await get_cache()
        return await cache.healthcheck()
    except Exception as exc:
        return {"name": "cache", "healthy": False, "error": type(exc).__name__}
