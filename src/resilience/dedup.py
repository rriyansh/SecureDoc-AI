"""In-flight request deduplication.

Use case
--------
A flaky client retries a slow request; both copies arrive within
``DEDUP_WINDOW_SECONDS``. We can't cancel the in-flight one, but we can:
* record the duplicate (metric, audit) so operators see it
* (optionally) short-circuit the second call to the cache

This module only *detects* duplicates — the caller decides the action
(typically: log, increment metric, allow cache to serve).

Implementation
--------------
For every ``(principal, question)`` tuple, hash the parts and store the hash
with a monotonic timestamp. On lookup, first prune entries older than the
window, then check presence. Pruning is O(expired) amortised — cheap.

Concurrency
-----------
Single lock, O(1) operations. Same cleanup pattern as the rate limiters.
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any

from src.core.config import get_settings
from src.core.logger import get_logger
from src.observability.metrics import DEDUP_HITS

log = get_logger("resilience.dedup")

_CLEANUP_EVERY_OPS = 200


class Deduplicator:
    """Window-based duplicate detector — never blocks."""

    def __init__(self, *, window_seconds: int = 30) -> None:
        if window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")
        self.window = float(window_seconds)
        self._seen: dict[str, float] = {}  # hash → monotonic timestamp
        self._lock = threading.Lock()
        self._ops = 0
        self._total_duplicates = 0

    @staticmethod
    def _hash_parts(parts: tuple[str, ...]) -> str:
        h = hashlib.sha256()
        for p in parts:
            h.update(p.encode("utf-8"))
            h.update(b"|")
        return h.hexdigest()

    def _cleanup(self, now: float) -> None:
        cutoff = now - self.window
        stale = [k for k, ts in self._seen.items() if ts < cutoff]
        for k in stale:
            del self._seen[k]
        if stale:
            log.debug(f"Dedup cleanup: dropped {len(stale)} expired keys")

    def is_duplicate(self, *parts: str) -> bool:
        """Return True if the same tuple was seen within the window.

        **Always** records the tuple — first call returns False (not a dup),
        subsequent calls within window return True.
        """
        if not parts:
            raise ValueError("at least one part required")
        key = self._hash_parts(parts)
        now = time.monotonic()

        with self._lock:
            self._ops += 1
            if self._ops >= _CLEANUP_EVERY_OPS:
                self._cleanup(now)
                self._ops = 0

            if key in self._seen:
                self._total_duplicates += 1
                DEDUP_HITS.inc()
                log.debug(f"Dedup hit: {key[:8]}...")
                return True

            self._seen[key] = now
            return False

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "tracked": len(self._seen),
                "window_seconds": self.window,
                "total_duplicates": self._total_duplicates,
            }

    def reset(self) -> None:
        with self._lock:
            self._seen.clear()
            self._ops = 0


# --------------------------------------------------------------------------- #
# Singleton                                                                    #
# --------------------------------------------------------------------------- #

_dedup: Deduplicator | None = None


def get_deduplicator() -> Deduplicator:
    """Return the process-wide deduplicator (built once from settings)."""
    global _dedup
    if _dedup is None:
        s = get_settings()
        _dedup = Deduplicator(window_seconds=s.dedup_window_seconds)
        log.info(f"Deduplicator initialized (window={s.dedup_window_seconds}s)")
    return _dedup
