"""Tests for cache."""

import time

from src.cache import TTLCache, cache_key


def test_get_set():
    c = TTLCache(max_size=10, ttl_seconds=60)
    c.set("k", "v")
    assert c.get("k") == "v"


def test_expires():
    c = TTLCache(max_size=10, ttl_seconds=1)
    c.set("k", "v")
    time.sleep(1.1)
    assert c.get("k") is None


def test_lru_eviction():
    c = TTLCache(max_size=2, ttl_seconds=60)
    c.set("a", "1"); c.set("b", "2"); c.set("c", "3")
    assert c.get("a") is None


def test_cache_key():
    assert cache_key("a", "b") == cache_key("a", "b")
    assert cache_key("a", "b") != cache_key("a", "c")


def test_encrypted_cache():
    c = TTLCache(max_size=10, ttl_seconds=60, encrypt=True)
    c.set("k", "secret")
    assert c.get("k") == "secret"
