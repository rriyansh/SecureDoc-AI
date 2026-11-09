"""In-memory token-bucket rate limiter per principal."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from fastapi import HTTPException, status

from src.config import get_settings
from src.logger import get_logger
from src.metrics import RATE_LIMIT_HITS

log = get_logger("rate_limiter")
_IDLE_CUTOFF = 300  # seconds
_CLEANUP_INTERVAL = 200  # operations


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
        self._op_count = 0

    def _cleanup_locked(self, now: float) -> None:
        stale = [k for k, b in self._buckets.items() if now - b.last_refill > _IDLE_CUTOFF]
        for k in stale:
            del self._buckets[k]

    def _consume(self, principal: str, cost: float = 1.0) -> tuple[bool, float]:
        now = time.monotonic()
        with self._lock:
            self._op_count += 1
            if self._op_count >= _CLEANUP_INTERVAL:
                self._cleanup_locked(now)
                self._op_count = 0

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
            retry_after = deficit / self.refill if self.refill > 0 else 60
            return False, retry_after

    def check(self, principal: str, cost: float = 1.0) -> None:
        ok, info = self._consume(principal, cost)
        if not ok:
            RATE_LIMIT_HITS.inc()
            log.warning(f"Rate limit: {principal} (retry {info:.1f}s)")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": f"{int(info) + 1}"},
            )

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"principals": len(self._buckets)}


_limiter: TokenBucketLimiter | None = None


def get_limiter() -> TokenBucketLimiter:
    global _limiter
    if _limiter is None:
        s = get_settings()
        _limiter = TokenBucketLimiter(s.rate_limit_per_minute, s.rate_limit_burst)
    return _limiter
