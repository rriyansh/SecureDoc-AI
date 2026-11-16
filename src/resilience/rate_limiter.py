"""Rate limiters: token bucket and sliding window.

Two algorithms, same ``check(principal)`` API:

* **TokenBucketLimiter** — allows bursts up to ``burst`` tokens, refills at
  ``per_minute / 60`` tokens/sec. Best for interactive APIs where occasional
  bursts (page reloads, retries) are legitimate.

* **SlidingWindowLimiter** — strict count over a rolling 60-second window.
  Best for cost-sensitive endpoints where you don't want any burst — each
  principal gets exactly ``per_minute`` calls per minute.

Cleanup
-------
Stale principals (idle > 5 min) are dropped opportunistically every 200 ops.
Prevents memory growth from abandoned clients. No background threads.

Concurrency
-----------
Single ``threading.Lock`` per limiter. All operations are O(1) except
sliding-window's periodic prune (bounded by window size, typically small).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

from src.core.config import get_settings
from src.core.exceptions import RateLimitError
from src.core.logger import get_logger
from src.observability.metrics import RATE_LIMIT_HITS

log = get_logger("resilience.rate_limiter")

# Drop a principal's entry if idle for this long
_IDLE_CUTOFF_SECONDS = 300.0
# Run cleanup every N operations
_CLEANUP_EVERY_OPS = 200


# --------------------------------------------------------------------------- #
# Token bucket                                                                 #
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class _Bucket:
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)


class TokenBucketLimiter:
    """Per-principal token bucket limiter with burst tolerance."""

    def __init__(self, *, per_minute: int, burst: int) -> None:
        if per_minute < 1:
            raise ValueError("per_minute must be >= 1")
        if burst < 1:
            raise ValueError("burst must be >= 1")

        self.per_minute = per_minute
        self.burst = burst
        self.refill_per_sec = per_minute / 60.0

        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()
        self._ops = 0
        self._total_rejections = 0

    def _cleanup(self, now: float) -> None:
        stale = [
            k for k, b in self._buckets.items()
            if now - b.last_refill > _IDLE_CUTOFF_SECONDS
        ]
        for k in stale:
            del self._buckets[k]
        if stale:
            log.debug(f"TokenBucket cleanup: dropped {len(stale)} stale principals")

    def _consume(self, principal: str, cost: float) -> tuple[bool, float]:
        """Return ``(admitted, info)``. ``info`` = remaining tokens or retry secs."""
        now = time.monotonic()
        with self._lock:
            self._ops += 1
            if self._ops >= _CLEANUP_EVERY_OPS:
                self._cleanup(now)
                self._ops = 0

            b = self._buckets.get(principal)
            if b is None:
                b = _Bucket(tokens=float(self.burst))
                self._buckets[principal] = b

            elapsed = now - b.last_refill
            b.tokens = min(self.burst, b.tokens + elapsed * self.refill_per_sec)
            b.last_refill = now

            if b.tokens >= cost:
                b.tokens -= cost
                return True, b.tokens

            deficit = cost - b.tokens
            retry = deficit / self.refill_per_sec if self.refill_per_sec > 0 else 60.0
            self._total_rejections += 1
            return False, retry

    def check(self, principal: str, *, cost: float = 1.0) -> None:
        """Raise :class:`RateLimitError` if the caller is over budget."""
        if cost <= 0:
            raise ValueError("cost must be > 0")

        ok, info = self._consume(principal, cost)
        if not ok:
            retry_after = max(1, int(info) + 1)
            RATE_LIMIT_HITS.inc()
            log.warning(
                f"TokenBucket rate-limit: {principal} "
                f"retry_after={retry_after}s"
            )
            raise RateLimitError(
                f"Rate limit exceeded — retry in {retry_after}s",
                retry_after=retry_after,
            )

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "backend": "token_bucket",
                "per_minute": self.per_minute,
                "burst": self.burst,
                "principals": len(self._buckets),
                "total_rejections": self._total_rejections,
            }

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
            self._ops = 0


# --------------------------------------------------------------------------- #
# Sliding window                                                               #
# --------------------------------------------------------------------------- #

class SlidingWindowLimiter:
    """Per-principal sliding 60s window limiter (no burst)."""

    def __init__(self, *, per_minute: int, window_seconds: float = 60.0) -> None:
        if per_minute < 1:
            raise ValueError("per_minute must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        self.per_minute = per_minute
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._ops = 0
        self._total_rejections = 0

    def _cleanup(self, cutoff: float) -> None:
        empty = [
            k for k, q in self._hits.items()
            if not q or q[-1] < cutoff
        ]
        for k in empty:
            del self._hits[k]
        if empty:
            log.debug(f"SlidingWindow cleanup: dropped {len(empty)} stale principals")

    def check(self, principal: str, *, cost: int = 1) -> None:
        """Raise :class:`RateLimitError` if this call would exceed the window."""
        if cost < 1:
            raise ValueError("cost must be >= 1")

        now = time.monotonic()
        cutoff = now - self.window

        with self._lock:
            self._ops += 1
            if self._ops >= _CLEANUP_EVERY_OPS:
                self._cleanup(cutoff)
                self._ops = 0

            q = self._hits.setdefault(principal, deque())
            # Drop hits that have aged out of the window
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) + cost > self.per_minute:
                # Time until the oldest hit expires
                retry = max(1, int(self.window - (now - q[0])) + 1) if q else 60
                self._total_rejections += 1
                RATE_LIMIT_HITS.inc()
                log.warning(
                    f"SlidingWindow rate-limit: {principal} "
                    f"({len(q)}/{self.per_minute} in window) retry_after={retry}s"
                )
                raise RateLimitError(
                    f"Rate limit exceeded — retry in {retry}s",
                    retry_after=retry,
                )

            for _ in range(cost):
                q.append(now)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "backend": "sliding_window",
                "per_minute": self.per_minute,
                "window_seconds": self.window,
                "principals": len(self._hits),
                "total_rejections": self._total_rejections,
            }

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._ops = 0


# --------------------------------------------------------------------------- #
# Singleton                                                                    #
# --------------------------------------------------------------------------- #

Limiter = TokenBucketLimiter | SlidingWindowLimiter
_limiter: Limiter | None = None


def get_limiter() -> Limiter:
    """Return the process-wide rate limiter (built once from settings)."""
    global _limiter
    if _limiter is not None:
        return _limiter

    s = get_settings()
    strategy: Literal["token_bucket", "sliding_window"] = s.rate_limit_strategy

    if strategy == "sliding_window":
        _limiter = SlidingWindowLimiter(per_minute=s.rate_limit_per_minute)
    else:
        _limiter = TokenBucketLimiter(
            per_minute=s.rate_limit_per_minute,
            burst=s.rate_limit_burst,
        )

    log.info(
        f"Rate limiter initialized: strategy={strategy} "
        f"per_minute={s.rate_limit_per_minute}"
        + (f" burst={s.rate_limit_burst}" if strategy == "token_bucket" else "")
    )
    return _limiter
