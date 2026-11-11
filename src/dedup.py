"""In-flight request deduplication."""

from __future__ import annotations

import threading
import time
from typing import Any

from src.config import get_settings
from src.logger import get_logger
from src.utils import stable_hash

log = get_logger("dedup")


class Deduplicator:
    def __init__(self, window_seconds: int) -> None:
        self.window = window_seconds
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def is_duplicate(self, *parts: Any) -> bool:
        key = stable_hash(*(str(p) for p in parts))
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            for k in [k for k, ts in self._seen.items() if ts < cutoff]:
                del self._seen[k]
            if key in self._seen:
                return True
            self._seen[key] = now
            return False

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"tracked": len(self._seen)}


_dedup: Deduplicator | None = None


def get_deduplicator() -> Deduplicator:
    global _dedup
    if _dedup is None:
        s = get_settings()
        _dedup = Deduplicator(s.dedup_window_seconds)
    return _dedup
