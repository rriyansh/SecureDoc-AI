"""Token bucket + sliding window rate limiter with cleanup."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

from fastapi import HTTPException, status

from src.config import get_settings
from src.logger import get_logger
from src.metrics import RATE_LIMIT_HITS

log = get_logger("rate_limiter")
_IDLE_CUTOFF = 300
_CLEANUP_INTERVAL = 200


@dataclass
class Bucket:
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)


class TokenBucketLimiter:
    def __init__(self, per_minute: int, burst: int) -> None:
        self.per_minute = per_minute
        self.burst = burst
        self.refill = per_minute / 60.0 if per_minute > 0 else 0.0
        self._buckets: dict[str, Bucket] = {}
        self._lock = threading.Lock()
        self._ops = 0

    def _cleanup(self, now: float) -> None:
        stale = [k for k, b in self._buckets.items() if now - b.last_refill > _IDLE_CUTOFF]
        for k in stale:
            del self._buckets[k]

    def _consume(self, principal: str, cost: float = 1.0) -> tuple[bool, float]:
        now = time.monotonic()
        with self._lock:
            self._ops += 1
            if self._ops >= _CLEANUP_INTERVAL:
                self._cleanup(now)
                self._ops = 0

            b = self._buckets.get(principal)
            if b is None:
                b = Bucket(tokens=float(self.burst))
                self._buckets[principal] = b

            elapsed = now - b.last_refill
            b.tokens = min(self.burst, b.tokens + elapsed * self.refill)
            b.last_refill = now

            if b.tokens >= cost:
                b.tokens -= cost
                return True, b.tokens
            deficit = cost - b.tokens
            retry = deficit / self.refill if self.refill > 0 else 60
            return False, retry

    def check(self, principal: str, cost: float = 1.0) -> None:
        ok, info = self._consume(principal, cost)
        if not ok:
            RATE_LIMIT_HITS.inc()
            log.warning(f"Rate limit: {principal} retry={info:.1f}s")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": f"{int(info) + 1}"},
            )

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"principals": len(self._buckets)}


class SlidingWindowLimiter:
    """Sliding-window limiter (requests per window)."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self.window = 60.0
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, principal: str, cost: int = 1) -> None:
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            q = self._hits.setdefault(principal, deque())
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) + cost > self.per_minute:
                retry = max(1, int(self.window - (now - q[0])) if q else 60)
                RATE_LIMIT_HITS.inc()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(retry)},
                )
            for _ in range(cost):
                q.append(now)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"principals": len(self._hits)}


_limiter: TokenBucketLimiter | SlidingWindowLimiter | None = None


def get_limiter():
    global _limiter
    if _limiter is None:
        s = get_settings()
        if s.rate_limit_strategy == "sliding_window":
            _limiter = SlidingWindowLimiter(s.rate_limit_per_minute)
        else:
            _limiter = TokenBucketLimiter(s.rate_limit_per_minute, s.rate_limit_burst)
    return _limiter
