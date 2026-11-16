"""Redis-backed distributed cache.

Properties
----------
* **Distributed** — shared across all API replicas. Required for consistent
  rate-limit-adjacent behavior at scale.
* **TTL** — enforced by Redis (``SETEX``). No client-side expiry tracking.
* **Encryption** — same AES-GCM envelope as :class:`MemoryCache`.
* **Namespace** — every key is prefixed with ``{namespace}:`` so multiple
  tenants/apps can share a Redis instance.
* **Fail-open** — if Redis errors on ``get`` or ``set``, log + return miss
  (never raise into the request path). Healthcheck surfaces the failure.

Connection
----------
Client uses ``decode_responses=True`` — every stored value is a str (either
plaintext or base64-encrypted). This avoids bytes-vs-str pitfalls and the
underlying storage cost is negligible.

Failure modes
-------------
* Redis connection refused at startup → factory falls back to memory
* Redis dies mid-request → cache miss, request continues
* Redis slow (timeout) → ``socket_timeout`` (default 2s) trips, cache miss
"""

from __future__ import annotations

from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.cache.base import CacheBackend
from src.core.config import get_settings
from src.core.logger import get_logger
from src.observability.metrics import CACHE_HITS, CACHE_MISSES

log = get_logger("cache.redis")


class RedisCache(CacheBackend):
    """Redis cache backend with namespacing + optional encryption."""

    def __init__(
        self,
        client: Redis,
        *,
        namespace: str = "securedoc",
        ttl_seconds: int = 3600,
        encrypt: bool = False,
    ) -> None:
        self._client = client
        self._ns = namespace.strip(":") or "securedoc"
        self._ttl = ttl_seconds
        self._encrypt = encrypt

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _full_key(self, key: str) -> str:
        return f"{self._ns}:{key}"

    def _enc(self, value: str) -> str:
        if not self._encrypt:
            return value
        try:
            from src.security.crypto import encrypt

            return encrypt(value)
        except Exception as exc:
            log.warning(f"Redis cache encryption failed (storing plain): {exc}")
            return value

    def _dec(self, value: str) -> str:
        if not self._encrypt:
            return value
        try:
            from src.security.crypto import decrypt

            return decrypt(value)
        except Exception:
            # Value may be plaintext (e.g. written before encryption enabled).
            # Return as-is — better to serve possibly-plain value than miss.
            return value

    # ------------------------------------------------------------------ #
    # Interface                                                          #
    # ------------------------------------------------------------------ #

    async def get(self, key: str) -> str | None:
        try:
            raw = await self._client.get(self._full_key(key))
        except RedisError as exc:
            log.warning(f"Redis GET failed (treating as miss): {exc}")
            CACHE_MISSES.inc()
            return None

        if raw is None:
            CACHE_MISSES.inc()
            return None

        CACHE_HITS.inc()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return self._dec(raw)

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        stored = self._enc(value)
        try:
            await self._client.setex(self._full_key(key), ttl, stored)
        except RedisError as exc:
            log.warning(f"Redis SET failed: {exc}")

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(self._full_key(key))
        except RedisError as exc:
            log.warning(f"Redis DEL failed: {exc}")

    async def clear(self) -> None:
        """Delete all keys under this namespace. Bounded scan to avoid blocking."""
        pattern = f"{self._ns}:*"
        deleted = 0
        try:
            async for k in self._client.scan_iter(match=pattern, count=500):
                await self._client.delete(k)
                deleted += 1
            log.info(f"Redis cache cleared ({deleted} keys under '{self._ns}')")
        except RedisError as exc:
            log.error(f"Redis CLEAR failed after {deleted} keys: {exc}")

    async def stats(self) -> dict[str, Any]:
        try:
            info = await self._client.info("memory")
            keys = await self._client.dbsize()
            return {
                "backend": "redis",
                "namespace": self._ns,
                "keys_in_db": keys,
                "used_memory_human": info.get("used_memory_human", "?"),
                "encrypted": self._encrypt,
                "ttl_seconds": self._ttl,
            }
        except RedisError as exc:
            return {"backend": "redis", "error": type(exc).__name__}

    async def healthcheck(self) -> dict[str, Any]:
        try:
            pong = await self._client.ping()
            return {
                "name": "cache",
                "healthy": bool(pong),
                "backend": "redis",
            }
        except RedisError as exc:
            return {
                "name": "cache",
                "healthy": False,
                "backend": "redis",
                "error": type(exc).__name__,
            }

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except RedisError as exc:
            log.warning(f"Redis close failed: {exc}")


async def build() -> RedisCache:
    """Construct a :class:`RedisCache` from settings. Raises on connect failure."""
    s = get_settings()
    client = Redis.from_url(
        s.redis_url,
        socket_timeout=s.redis_socket_timeout,
        socket_connect_timeout=s.redis_socket_timeout,
        decode_responses=True,
        health_check_interval=30,
    )
    # Fail fast if unreachable
    await client.ping()
    log.info(f"Redis cache connected: {s.redis_url.split('@')[-1]}")
    return RedisCache(
        client,
        namespace=s.cache_namespace,
        ttl_seconds=s.cache_ttl_seconds,
        encrypt=s.cache_encrypt,
    )
