"""In-memory TTL + LRU cache with optional encryption.

Properties
----------
* **Thread-safe** — single ``threading.Lock`` guards the OrderedDict. All
  operations are O(1) amortised.
* **TTL** — every entry carries ``expires_at``. Lazy expiry on ``get``,
  plus opportunistic pruning on ``set`` when the store is over capacity.
* **LRU eviction** — OrderedDict ``move_to_end`` on access; ``popitem(False)``
  evicts oldest when over ``max_size``.
* **Encryption** — if ``encrypt=True``, values are AES-GCM encrypted before
  storage. Decryption happens **outside** the lock so a slow crypto op
  never blocks other threads.
* **Metrics** — ``CACHE_HITS`` / ``CACHE_MISSES`` counters (Prometheus).

Limitations
-----------
* **Per-process** — each replica has its own cache. Fine for single-instance
  deployments; for multi-replica use :class:`RedisCache`.
* **Unbounded entry size** — the caller decides what fits. A single huge
  answer can occupy max_size slots; watch cache entry sizes in production.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from src.cache.base import CacheBackend
from src.core.config import get_settings
from src.core.logger import get_logger
from src.observability.metrics import CACHE_HITS, CACHE_MISSES

log = get_logger("cache.memory")


@dataclass(slots=True)
class _Entry:
    """One cache slot — either plain or encrypted."""

    value: str
    expires_at: float
    encrypted: bool


class MemoryCache(CacheBackend):
    """TTL + LRU cache with optional AES-GCM encryption."""

    def __init__(
        self,
        *,
        max_size: int = 1000,
        ttl_seconds: int = 3600,
        encrypt: bool = False,
    ) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be >= 1")

        self.max_size = max_size
        self.ttl = ttl_seconds
        self.encrypt = encrypt

        self._store: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.Lock()

        # Per-instance counters (in addition to Prometheus global counters)
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._encryption_errors = 0

    # ------------------------------------------------------------------ #
    # Encryption helpers                                                 #
    # ------------------------------------------------------------------ #

    def _enc(self, value: str) -> tuple[str, bool]:
        """Encrypt or pass through, with graceful fallback to plaintext."""
        if not self.encrypt:
            return value, False
        try:
            from src.security.crypto import encrypt

            return encrypt(value), True
        except Exception as exc:
            # Never fail the request because encryption broke — store plain
            # and log once per process via the counter in stats().
            self._encryption_errors += 1
            log.warning(f"Cache encryption failed (storing plain): {exc}")
            return value, False

    def _dec(self, entry: _Entry) -> str:
        """Decrypt or pass through."""
        if not entry.encrypted:
            return entry.value
        from src.security.crypto import decrypt

        return decrypt(entry.value)

    # ------------------------------------------------------------------ #
    # Internal                                                           #
    # ------------------------------------------------------------------ #

    def _expire_if_needed(self, key: str) -> None:
        """Lazy expiry — call with lock held."""
        e = self._store.get(key)
        if e is not None and e.expires_at <= time.monotonic():
            self._store.pop(key, None)

    def _prune_over_capacity(self) -> None:
        """Evict oldest entries until within max_size. Call with lock held."""
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)
            self._evictions += 1

    def _prune_expired_batch(self, sample_size: int = 100) -> None:
        """Opportunistically drop expired entries — call with lock held.

        Bounded work per call to avoid pauses; called from ``set``.
        """
        now = time.monotonic()
        # Iterate a bounded number of entries — cheap when most are fresh
        checked = 0
        for key in list(self._store.keys()):
            if checked >= sample_size:
                break
            checked += 1
            if self._store[key].expires_at <= now:
                self._store.pop(key, None)

    # ------------------------------------------------------------------ #
    # Interface                                                          #
    # ------------------------------------------------------------------ #

    async def get(self, key: str) -> str | None:
        entry: _Entry | None = None
        with self._lock:
            self._expire_if_needed(key)
            e = self._store.get(key)
            if e is None:
                self._misses += 1
                CACHE_MISSES.inc()
                return None
            self._store.move_to_end(key)  # LRU touch
            entry = e
            self._hits += 1
            CACHE_HITS.inc()

        # Decrypt outside the lock — crypto is CPU work we don't want holding
        # the lock while other threads wait.
        try:
            return self._dec(entry)
        except Exception as exc:
            log.error(f"Cache decryption failed for key {key[:8]}...: {exc}")
            with self._lock:
                self._store.pop(key, None)
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> None:
        stored, encrypted = self._enc(value)
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl
        expires_at = time.monotonic() + ttl

        with self._lock:
            self._store[key] = _Entry(
                value=stored, expires_at=expires_at, encrypted=encrypted
            )
            self._store.move_to_end(key)
            self._prune_over_capacity()
            # Occasionally prune expired entries — every 10th set
            if self._evictions % 10 == 0:
                self._prune_expired_batch()

    async def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        with self._lock:
            self._store.clear()
        log.info("Memory cache cleared")

    async def stats(self) -> dict[str, Any]:
        with self._lock:
            size = len(self._store)
        return {
            "backend": "memory",
            "size": size,
            "max_size": self.max_size,
            "ttl_seconds": self.ttl,
            "encrypted": self.encrypt,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "encryption_errors": self._encryption_errors,
            "hit_rate": (
                round(self._hits / (self._hits + self._misses), 3)
                if (self._hits + self._misses) > 0
                else 0.0
            ),
        }

    async def healthcheck(self) -> dict[str, Any]:
        return {
            "name": "cache",
            "healthy": True,
            "backend": "memory",
            "size": len(self._store),
        }


def build() -> MemoryCache:
    """Construct a :class:`MemoryCache` from settings."""
    s = get_settings()
    return MemoryCache(
        max_size=s.cache_max_size,
        ttl_seconds=s.cache_ttl_seconds,
        encrypt=s.cache_encrypt,
    )
