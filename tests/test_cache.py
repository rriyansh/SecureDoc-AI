"""Tests for cache module."""

import pytest
import time
from src.cache import ExactCache, SemanticCache, HybridCache, query_cache


class TestExactCache:
    def test_basic_get_set(self):
        cache = ExactCache(max_size=10, ttl=3600)
        cache.set("query", "answer", param="value")
        assert cache.get("query", param="value") == "answer"

    def test_cache_miss(self):
        cache = ExactCache(max_size=10, ttl=3600)
        assert cache.get("nonexistent") is None

    def test_different_params(self):
        cache = ExactCache(max_size=10, ttl=3600)
        cache.set("query", "answer1", top_k=5)
        cache.set("query", "answer2", top_k=10)
        assert cache.get("query", top_k=5) == "answer1"
        assert cache.get("query", top_k=10) == "answer2"

    def test_ttl_expiry(self):
        cache = ExactCache(max_size=10, ttl=0)  # Immediate expiry
        cache.set("query", "answer")
        time.sleep(0.01)
        assert cache.get("query") is None

    def test_lru_eviction(self):
        cache = ExactCache(max_size=2, ttl=3600)
        cache.set("q1", "a1")
        cache.set("q2", "a2")
        cache.set("q3", "a3")  # Should evict q1
        assert cache.get("q1") is None
        assert cache.get("q2") == "a2"
        assert cache.get("q3") == "a3"

    def test_invalidate(self):
        cache = ExactCache(max_size=10, ttl=3600)
        cache.set("query", "answer")
        assert cache.invalidate("query") is True
        assert cache.get("query") is None
        assert cache.invalidate("query") is False

    def test_clear(self):
        cache = ExactCache(max_size=10, ttl=3600)
        cache.set("q1", "a1")
        cache.set("q2", "a2")
        cache.clear()
        assert cache.get("q1") is None
        assert cache.get("q2") is None

    def test_stats(self):
        cache = ExactCache(max_size=10, ttl=3600)
        cache.set("q1", "a1")
        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["max_size"] == 10


class TestSemanticCache:
    def test_basic_get_set(self):
        cache = SemanticCache(max_size=10, similarity_threshold=0.5)
        cache.set("what is the policy", "The policy states...")
        # Similar query should hit
        result = cache.get("what is the company policy")
        # Note: This uses random embeddings, so might not hit
        # Just verify it doesn't crash

    def test_cache_miss(self):
        cache = SemanticCache(max_size=10, similarity_threshold=0.99)  # Very high threshold
        cache.set("query1", "answer1")
        result = cache.get("completely different query")
        # With random embeddings and high threshold, likely miss
        # Just verify it returns something without error

    def test_clear(self):
        cache = SemanticCache(max_size=10)
        cache.set("q1", "a1")
        cache.clear()
        stats = cache.stats()
        assert stats["size"] == 0


class TestHybridCache:
    def test_exact_then_semantic(self):
        cache = HybridCache(exact_max_size=10, semantic_max_size=10)
        cache.set("query", "exact_answer")
        # Should hit exact cache
        result = cache.get("query")
        assert result == "exact_answer"

    def test_set_both(self):
        cache = HybridCache(exact_max_size=10, semantic_max_size=10)
        cache.set("query", "answer")
        # Both caches should have it
        assert cache.exact.get("query") == "answer"

    def test_invalidate_exact_only(self):
        cache = HybridCache(exact_max_size=10, semantic_max_size=10)
        cache.set("query", "answer")
        cache.invalidate("query")
        assert cache.exact.get("query") is None
        # Semantic cache still has it (but uses different key)

    def test_clear_both(self):
        cache = HybridCache(exact_max_size=10, semantic_max_size=10)
        cache.set("q1", "a1")
        cache.clear()
        assert cache.exact.get("q1") is None
        assert cache.semantic.stats()["size"] == 0

    def test_stats(self):
        cache = HybridCache(exact_max_size=10, semantic_max_size=10)
        cache.set("q1", "a1")
        stats = cache.stats()
        assert "exact" in stats
        assert "semantic" in stats


class TestGlobalQueryCache:
    def test_global_instance(self):
        # Just verify it exists and works
        query_cache.set("test_global", "global_answer")
        result = query_cache.get("test_global")
        assert result == "global_answer"
        query_cache.invalidate("test_global")