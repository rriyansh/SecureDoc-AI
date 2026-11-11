"""Behavioral anomaly detection (rapid-fire, high-entropy)."""

from __future__ import annotations

import math
import threading
import time
from collections import Counter, deque

from src.config import get_settings
from src.logger import get_logger

log = get_logger("anomaly")


class AnomalyDetector:
    def __init__(self, threshold: int, window_seconds: int) -> None:
        self.threshold = threshold
        self.window = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._payloads: dict[str, deque[str]] = {}
        self._lock = threading.Lock()

    def _entropy(self, text: str) -> float:
        if not text:
            return 0.0
        counts = Counter(text)
        total = len(text)
        return -sum((c / total) * math.log2(c / total) for c in counts.values())

    def check(self, principal: str, payload: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            q = self._events.setdefault(principal, deque())
            while q and q[0] < cutoff:
                q.popleft()
            q.append(now)

            p = self._payloads.setdefault(principal, deque(maxlen=20))
            p.append(payload[:200])

            if len(q) > self.threshold:
                log.warning(f"Anomaly: rapid-fire by {principal} ({len(q)} in {self.window}s)")

            if len(p) >= 5 and len(set(p)) == 1:
                log.warning(f"Anomaly: repeated payload by {principal}")

            ent = self._entropy(payload)
            if ent > 5.5 and len(payload) > 100:
                log.warning(f"Anomaly: high-entropy payload by {principal} (H={ent:.2f})")


_detector: AnomalyDetector | None = None


def get_detector() -> AnomalyDetector:
    global _detector
    if _detector is None:
        s = get_settings()
        _detector = AnomalyDetector(s.anomaly_threshold, s.anomaly_window_seconds)
    return _detector


def check(principal: str, payload: str) -> None:
    if not get_settings().anomaly_detection_enabled:
        return
    get_detector().check(principal, payload)
