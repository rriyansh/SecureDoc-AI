"""Tests for rate limiters."""

import pytest
from fastapi import HTTPException

from src.rate_limiter import SlidingWindowLimiter, TokenBucketLimiter


def test_burst_allowed():
    lim = TokenBucketLimiter(per_minute=60, burst=3)
    for _ in range(3):
        lim.check("p1")


def test_blocks_after_burst():
    lim = TokenBucketLimiter(per_minute=60, burst=2)
    lim.check("p1"); lim.check("p1")
    with pytest.raises(HTTPException) as e:
        lim.check("p1")
    assert e.value.status_code == 429


def test_per_principal():
    lim = TokenBucketLimiter(per_minute=60, burst=1)
    lim.check("a"); lim.check("b")


def test_sliding_window():
    lim = SlidingWindowLimiter(per_minute=2)
    lim.check("p")
    lim.check("p")
    with pytest.raises(HTTPException):
        lim.check("p")
