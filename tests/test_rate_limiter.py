"""Tests for rate limiter module."""

import pytest
import time
from src.rate_limiter import (
    TokenBucket,
    RateLimiter,
    SlidingWindowRateLimiter,
    api_rate_limiter,
    query_rate_limiter,
    get_rate_limiter,
)


class TestTokenBucket:
    def test_initial_tokens(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.get_available() == 10

    def test_consume_success(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(5) is True
        assert bucket.get_available() == 5

    def test_consume_failure(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(15) is False
        assert bucket.get_available() == 10

    def test_refill_over_time(self):
        bucket = TokenBucket(capacity=10, refill_rate=10.0)
        bucket.consume(10)
        assert bucket.get_available() == 0

        time.sleep(0.2)  # 200ms * 10 tokens/sec = 2 tokens
        available = bucket.get_available()
        assert 1.5 <= available <= 2.5

    def test_get_retry_after(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.consume(10)
        retry = bucket.get_retry_after(5)
        assert 4.5 <= retry <= 5.5


class TestRateLimiter:
    def test_default_limits(self):
        limiter = RateLimiter(default_capacity=10, default_refill_rate=1.0)
        allowed, info = limiter.check_limit("test_key")
        assert allowed is True
        assert info["limit"] == 10

    def test_custom_limits(self):
        limiter = RateLimiter()
        limiter.set_limit("custom_key", 100, 10.0)
        allowed, info = limiter.check_limit("custom_key")
        assert info["limit"] == 100

    def test_rate_limit_exceeded(self):
        limiter = RateLimiter(default_capacity=2, default_refill_rate=0)
        limiter.check_limit("limited_key")
        limiter.check_limit("limited_key")
        allowed, info = limiter.check_limit("limited_key")
        assert allowed is False
        assert info["remaining"] == 0

    def test_separate_keys(self):
        limiter = RateLimiter(default_capacity=1, default_refill_rate=0)
        assert limiter.check_limit("key1")[0] is True
        assert limiter.check_limit("key2")[0] is True
        assert limiter.check_limit("key1")[0] is False

    def test_get_status(self):
        limiter = RateLimiter(default_capacity=10, default_refill_rate=1.0)
        status = limiter.get_status("test_key")
        assert status["limit"] == 10
        assert status["remaining"] <= 10


class TestSlidingWindowRateLimiter:
    def test_basic_limit(self):
        limiter = SlidingWindowRateLimiter(window_size=1, max_requests=2)
        assert limiter.check_limit("key")[0] is True
        assert limiter.check_limit("key")[0] is True
        assert limiter.check_limit("key")[0] is False

    def test_window_expiry(self):
        limiter = SlidingWindowRateLimiter(window_size=0.1, max_requests=1)
        assert limiter.check_limit("key")[0] is True
        assert limiter.check_limit("key")[0] is False
        time.sleep(0.15)
        assert limiter.check_limit("key")[0] is True


class TestGlobalLimiters:
    def test_get_rate_limiter_api(self):
        limiter = get_rate_limiter("api")
        assert limiter is api_rate_limiter

    def test_get_rate_limiter_query(self):
        limiter = get_rate_limiter("query")
        assert limiter is query_rate_limiter

    def test_get_rate_limiter_default(self):
        limiter = get_rate_limiter("unknown")
        assert limiter is api_rate_limiter

    def test_api_limiter_defaults(self):
        allowed, info = api_rate_limiter.check_limit("test_api")
        assert info["limit"] == 100

    def test_query_limiter_stricter(self):
        allowed, info = query_rate_limiter.check_limit("test_query")
        assert info["limit"] == 20