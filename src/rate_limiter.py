"""Token bucket rate limiter for API protection."""

import time
import threading
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if successful."""
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_available(self) -> float:
        """Get current available tokens."""
        with self._lock:
            self._refill()
            return self.tokens

    def get_retry_after(self, tokens: int = 1) -> float:
        """Get seconds until tokens are available."""
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                return 0.0
            return (tokens - self.tokens) / self.refill_rate


class RateLimiter:
    """Token bucket rate limiter with per-key buckets."""

    def __init__(
        self,
        default_capacity: int = 100,
        default_refill_rate: float = 10.0,
        cleanup_interval: int = 300,
    ):
        self.default_capacity = default_capacity
        self.default_refill_rate = default_refill_rate
        self.cleanup_interval = cleanup_interval
        self._buckets: Dict[str, TokenBucket] = {}
        self._bucket_configs: Dict[str, Tuple[int, float]] = {}
        self._lock = threading.RLock()
        self._last_cleanup = time.monotonic()

    def _get_bucket(self, key: str) -> TokenBucket:
        """Get or create a token bucket for a key."""
        with self._lock:
            if key not in self._buckets:
                capacity, refill_rate = self._bucket_configs.get(
                    key, (self.default_capacity, self.default_refill_rate)
                )
                self._buckets[key] = TokenBucket(capacity, refill_rate)
            return self._buckets[key]

    def set_limit(self, key: str, capacity: int, refill_rate: float) -> None:
        """Set custom limit for a key."""
        with self._lock:
            self._bucket_configs[key] = (capacity, refill_rate)
            if key in self._buckets:
                self._buckets[key] = TokenBucket(capacity, refill_rate)

    def check_limit(self, key: str, tokens: int = 1) -> Tuple[bool, Dict[str, float]]:
        """
        Check if request is allowed.
        Returns (allowed, info_dict) where info_dict contains rate limit metadata.
        """
        bucket = self._get_bucket(key)
        allowed = bucket.consume(tokens)
        available = bucket.get_available()
        retry_after = bucket.get_retry_after(tokens)

        # Periodic cleanup of unused buckets
        now = time.monotonic()
        if now - self._last_cleanup > self.cleanup_interval:
            self._cleanup_old_buckets(now)

        return allowed, {
            "limit": bucket.capacity,
            "remaining": max(0, available),
            "retry_after": retry_after,
            "reset_at": time.monotonic() + retry_after if retry_after > 0 else None,
        }

    def _cleanup_old_buckets(self, now: float) -> None:
        """Remove buckets that haven't been used recently."""
        with self._lock:
            to_remove = []
            for key, bucket in self._buckets.items():
                if now - bucket.last_refill > self.cleanup_interval * 2:
                    to_remove.append(key)
            for key in to_remove:
                del self._buckets[key]
            self._last_cleanup = now
            if to_remove:
                logger.debug("Cleaned up %d unused rate limit buckets", len(to_remove))

    def get_status(self, key: str) -> Dict[str, float]:
        """Get current rate limit status for a key."""
        bucket = self._get_bucket(key)
        return {
            "limit": bucket.capacity,
            "remaining": max(0, bucket.get_available()),
            "reset_at": time.monotonic() + bucket.get_retry_after(1),
        }


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for more precise limiting."""

    def __init__(self, window_size: int = 60, max_requests: int = 100):
        self.window_size = window_size
        self.max_requests = max_requests
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()

    def check_limit(self, key: str) -> Tuple[bool, Dict[str, int]]:
        """Check if request is allowed under sliding window."""
        with self._lock:
            now = time.time()
            window_start = now - self.window_size

            # Remove old requests
            self._requests[key] = [ts for ts in self._requests[key] if ts > window_start]

            allowed = len(self._requests[key]) < self.max_requests
            if allowed:
                self._requests[key].append(now)

            remaining = max(0, self.max_requests - len(self._requests[key]))
            reset_at = int(now + self.window_size)

            return allowed, {
                "limit": self.max_requests,
                "remaining": remaining,
                "reset_at": reset_at,
            }


# Global rate limiter instances
api_rate_limiter = RateLimiter(
    default_capacity=100,
    default_refill_rate=10.0,
)

# Stricter limiter for expensive operations
query_rate_limiter = RateLimiter(
    default_capacity=20,
    default_refill_rate=2.0,
)


def get_rate_limiter(scope: str = "api") -> RateLimiter:
    """Get rate limiter for a specific scope."""
    if scope == "query":
        return query_rate_limiter
    return api_rate_limiter