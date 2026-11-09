"""Thread-safe TTL + LRU cache."""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from src.config import get_settings
from src.metrics import CACHE_HITS, CACHE_MISSES


@dataclass
class Entry:
    value: str
    expires_at: float


class TTLCache:
    def __init__(self, max_size: int, ttl_seconds: int) -> None:
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._store: OrderedDict[str, Entry] = OrderedDict()
        self._lock = threading.Lock()

    def _expire(self, key: str) -> None:
        e = self._store.get(key)
        if e and e.expires_at <= time.monotonic():
            self._store.pop(key, None)

    def get(self, key: str) -> str | None:
        with self._lock:
            self._expire(key)
            if key not in self._store:
                CACHE_MISSES.inc()
                return None
            self._store.move_to_end(key)
            CACHE_HITS.inc()
            return self._store[key].value

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._store[key] = Entry(value=value, expires_at=time.monotonic() + self.ttl)
            self._store.move_to_end(key)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"size": len(self._store), "max_size": self.max_size}


def cache_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()


_response_cache: TTLCache | None = None


def get_response_cache() -> TTLCache:
    global _response_cache
    if _response_cache is None:
        s = get_settings()
        _response_cache = TTLCache(s.cache_max_size, s.cache_ttl_seconds)
    return _response_cache
