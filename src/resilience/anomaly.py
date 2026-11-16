"""Behavioral anomaly detection.

Three heuristics, all running **in-band** (no separate worker):

1. **Rapid-fire** — more than ``threshold`` events per ``window_seconds``
   for a principal. Catches automated scrapers and injection fuzzers.
2. **Repeated payload** — 5+ identical payloads in the recent queue.
   Catches retry storms and deduplication failures.
3. **High-entropy payload** — Shannon entropy > 5.5 bits/char AND
   length > 100. Catches encoded/packed attacks that slip past regex.

Action
------
**Detection only.** Logs at WARNING and increments ``ANOMALY_HITS`` with a
``kind`` label. Callers can hook alerts on the counter; no request is
blocked here (that's the rate limiter's job).
"""

from __future__ import annotations

import math
import threading
import time
from collections import Counter, deque
from typing import Any

from src.core.config import get_settings
from src.core.logger import get_logger
from src.observability.metrics import ANOMALY_HITS

log = get_logger("resilience.anomaly")

# Entropy threshold above which a payload is suspicious
_ENTROPY_THRESHOLD = 5.5
# Minimum length for entropy heuristic
_ENTROPY_MIN_LENGTH = 100
# History for repeated-payload detection
_REPEAT_QUEUE_SIZE = 20
# Cleanup frequency (ops)
_CLEANUP_EVERY_OPS = 200


def _shannon_entropy(text: str) -> float:
    """Shannon entropy in bits per character. 0 for empty strings."""
    if not text:
        return 0.0
    counts = Counter(text)
    total = len(text)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


class AnomalyDetector:
    """Per-principal anomaly heuristics — never blocks requests."""

    def __init__(
        self,
        *,
        threshold: int = 20,
        window_seconds: int = 10,
    ) -> None:
        if threshold < 1:
            raise ValueError("threshold must be >= 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")

        self.threshold = threshold
        self.window = float(window_seconds)

        self._events: dict[str, deque[float]] = {}
        self._payloads: dict[str, deque[str]] = {}
        self._lock = threading.Lock()
        self._ops = 0

        # Counts for /admin stats
        self._rapid_fire_hits = 0
        self._repeated_hits = 0
        self._entropy_hits = 0

    def _cleanup(self, cutoff: float) -> None:
        empty = [k for k, q in self._events.items() if not q or q[-1] < cutoff]
        for k in empty:
            self._events.pop(k, None)
            self._payloads.pop(k, None)
        if empty:
            log.debug(f"Anomaly cleanup: dropped {len(empty)} stale principals")

    def check(self, principal: str, payload: str) -> None:
        """Run all heuristics. Logs + increments metrics on detection."""
        now = time.monotonic()
        cutoff = now - self.window

        with self._lock:
            self._ops += 1
            if self._ops >= _CLEANUP_EVERY_OPS:
                self._cleanup(cutoff)
                self._ops = 0

            # Rapid-fire tracking
            events = self._events.setdefault(principal, deque())
            while events and events[0] < cutoff:
                events.popleft()
            events.append(now)
            rapid = len(events) > self.threshold

            # Repeated-payload tracking
            queue = self._payloads.setdefault(principal, deque(maxlen=_REPEAT_QUEUE_SIZE))
            queue.append(payload[:200])  # truncate for storage
            repeated = (
                len(queue) >= 5
                and len(set(queue)) == 1
            )

            # Entropy heuristic
            entropy = _shannon_entropy(payload) if len(payload) >= _ENTROPY_MIN_LENGTH else 0.0
            suspicious_entropy = entropy > _ENTROPY_THRESHOLD

            # Increment hit counters under lock (avoids extra lock cycles)
            if rapid:
                self._rapid_fire_hits += 1
                ANOMALY_HITS.labels(kind="rapid").inc()
            if repeated:
                self._repeated_hits += 1
                ANOMALY_HITS.labels(kind="repeated").inc()
            if suspicious_entropy:
                self._entropy_hits += 1
                ANOMALY_HITS.labels(kind="entropy").inc()

        # Log outside lock
        if rapid:
            log.warning(
                f"Anomaly rapid-fire: {principal} "
                f"({len(events)} events in {self.window:.0f}s, "
                f"threshold={self.threshold})"
            )
        if repeated:
            log.warning(
                f"Anomaly repeated payload: {principal} "
                f"({len(queue)} identical payloads)"
            )
        if suspicious_entropy:
            log.warning(
                f"Anomaly high-entropy payload: {principal} "
                f"(H={entropy:.2f} bits/char, len={len(payload)})"
            )

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "principals_tracked": len(self._events),
                "threshold": self.threshold,
                "window_seconds": self.window,
                "rapid_fire_hits": self._rapid_fire_hits,
                "repeated_hits": self._repeated_hits,
                "entropy_hits": self._entropy_hits,
            }

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._payloads.clear()
            self._ops = 0


# --------------------------------------------------------------------------- #
# Singleton                                                                    #
# --------------------------------------------------------------------------- #

_detector: AnomalyDetector | None = None


def get_detector() -> AnomalyDetector:
    """Return the process-wide anomaly detector (built once from settings)."""
    global _detector
    if _detector is None:
        s = get_settings()
        _detector = AnomalyDetector(
            threshold=s.anomaly_threshold,
            window_seconds=s.anomaly_window_seconds,
        )
        log.info(
            f"Anomaly detector initialized "
            f"(threshold={s.anomaly_threshold}, "
            f"window={s.anomaly_window_seconds}s)"
        )
    return _detector


def check_anomaly(principal: str, payload: str) -> None:
    """Convenience: run anomaly detection if enabled in settings."""
    if not get_settings().anomaly_detection_enabled:
        return
    get_detector().check(principal, payload)
