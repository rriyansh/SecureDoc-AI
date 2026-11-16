"""Cache interface and helpers.

The :class:`CacheBackend` ABC is the **only** contract callers should depend
on. Do not reach into :class:`MemoryCache` or :class:`RedisCache` directly —
they're internal to the ``src.cache`` package.

Why async methods: even the memory cache is called from async FastAPI
handlers, and Redis is inherently async. Uniform interface = no branching at
call sites.

Key format
----------
:func:`make_cache_key` produces a hex digest from arbitrary string parts.
Two callers with the same parts get the same key; the ``namespace`` parameter
lets you scope keys (e.g. per-principal) without changing call sites.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import Any


class CacheBackend(ABC):
    """Async cache interface — implemented by every backend."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Return the stored value or ``None``. Must not raise on miss."""

    @abstractmethod
    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store ``value`` at ``key``. If ``ttl_seconds`` is ``None``, use default."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a single key. No-op on miss."""

    @abstractmethod
    async def clear(self) -> None:
        """Remove all keys in this cache's namespace."""

    @abstractmethod
    async def stats(self) -> dict[str, Any]:
        """Return backend-specific stats (size, hits, misses, encrypted, ...)."""

    @abstractmethod
    async def healthcheck(self) -> dict[str, Any]:
        """Return ``{"name": "...", "healthy": bool}`` for ``/health/deps``."""

    async def close(self) -> None:
        """Release resources. Override in backends that hold connections."""
        return None


class NullCache(CacheBackend):
    """No-op cache — returned when ``CACHE_ENABLED=false``.

    Callers never branch on cache presence; this class makes "no cache" a
    transparent drop-in.
    """

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None

    async def clear(self) -> None:
        return None

    async def stats(self) -> dict[str, Any]:
        return {"backend": "null", "enabled": False}

    async def healthcheck(self) -> dict[str, Any]:
        return {"name": "cache", "healthy": True, "backend": "null"}


def make_cache_key(*parts: str, namespace: str = "") -> str:
    """Derive a deterministic key from arbitrary string parts.

    Parameters
    ----------
    *parts : str
        Values to hash in order. Typically ``(principal, question)``.
    namespace : str
        Optional namespace prefix — hashed in so two namespaces never collide.

    Returns
    -------
    str
        64-character hex digest, safe for all backends.

    Example
    -------
    >>> make_cache_key("user:1", "how long is retention?")
    'a3f1...'
    >>> make_cache_key("user:1", "how long is retention?", namespace="v4")
    'b7c2...'  # different key
    """
    h = hashlib.sha256()
    if namespace:
        h.update(namespace.encode("utf-8"))
        h.update(b"|")
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()
