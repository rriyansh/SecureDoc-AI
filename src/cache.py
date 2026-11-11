"""Thread-safe TTL + LRU cache with optional AES-GCM encryption."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable

from src.config import get_settings
from src.logger import get_logger
from src.metrics import CACHE_HITS, CACHE_MISSES

log = get_logger("cache")


@dataclass
class Entry:
    value: str
    expires_at: float
    encrypted: bool


class TTLCache:
    def __init__(
        self,
        max_size: int,
        ttl_seconds: int,
        encrypt: bool = False,
    ) -> None:
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.encrypt = encrypt
        self._store: OrderedDict[str, Entry] = OrderedDict()
        self._lock = threading.Lock()

    def _encrypt(self, value: str) -> tuple[str, bool]:
        if not self.encrypt:
            return value, False
        try:
            from src.crypto import encrypt
            return encrypt(value), True
        except Exception as exc:
            log.warning(f"Encryption failed, storing plaintext: {exc}")
            return value, False

    def _decrypt(self, entry: Entry) -> str:
        if not entry.encrypted:
            return entry.value
        from src.crypto import decrypt
        return decrypt(entry.value)

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
            entry = self._store[key]
            CACHE_HITS.inc()
        try:
            return self._decrypt(entry)
        except Exception as exc:
            log.error(f"Decryption failed: {exc}")
            with self._lock:
                self._store.pop(key, None)
            return None

    def set(self, key: str, value: str) -> None:
        stored, encrypted = self._encrypt(value)
        with self._lock:
            self._store[key] = Entry(
                value=stored,
                expires_at=time.monotonic() + self.ttl,
                encrypted=encrypted,
            )
            self._store.move_to_end(key)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def stats(self) -> dict[str, int | bool]:
        with self._lock:
            return {"size": len(self._store), "max_size": self.max_size, "encrypted": self.encrypt}


def cache_key(*parts: str) -> str:
    import hashlib

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
        _response_cache = TTLCache(s.cache_max_size, s.cache_ttl_seconds, s.cache_encrypt)
    return _response_cache
