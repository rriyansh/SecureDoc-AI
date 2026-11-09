"""Semantic and exact caching for query results."""

import hashlib
import json
import time
import threading
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict

import numpy as np

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    embedding: Optional[np.ndarray] = None
    metadata: Dict = field(default_factory=dict)


class ExactCache:
    """LRU cache for exact key matches."""

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

    def _make_key(self, query: str, **params) -> str:
        """Generate cache key from query and parameters."""
        key_data = {"query": query, **params}
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]

    def get(self, query: str, **params) -> Optional[Any]:
        """Get value from cache if exists and not expired."""
        key = self._make_key(query, **params)
        with self._lock:
            if key not in self._cache:
                return None
            entry = self._cache[key]
            if time.time() - entry.created_at > self.ttl:
                del self._cache[key]
                return None
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._cache.move_to_end(key)
            return entry.value

    def set(self, query: str, value: Any, **params) -> None:
        """Set value in cache."""
        key = self._make_key(query, **params)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                metadata=params,
            )
            self._cache[key] = entry

    def invalidate(self, query: str, **params) -> bool:
        """Invalidate a specific cache entry."""
        key = self._make_key(query, **params)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl": self.ttl,
                "entries": [
                    {
                        "key": k[:8] + "...",
                        "age": time.time() - v.created_at,
                        "access_count": v.access_count,
                    }
                    for k, v in list(self._cache.items())[:10]
                ],
            }


class SemanticCache:
    """Semantic cache using embedding similarity."""

    def __init__(
        self,
        max_size: int = 500,
        similarity_threshold: float = 0.85,
        ttl: int = 3600,
    ):
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold
        self.ttl = ttl
        self._cache: List[CacheEntry] = []
        self._lock = threading.RLock()

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text. Placeholder for actual embedding model."""
        return np.random.rand(1536).astype(np.float32)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def get(self, query: str, **params) -> Optional[Any]:
        """Get semantically similar cached result."""
        query_embedding = self._get_embedding(query)
        with self._lock:
            now = time.time()
            best_match = None
            best_score = 0.0
            for entry in self._cache:
                if now - entry.created_at > self.ttl:
                    continue
                if entry.embedding is not None:
                    score = self._cosine_similarity(query_embedding, entry.embedding)
                    if score > best_score and score >= self.similarity_threshold:
                        best_score = score
                        best_match = entry
            if best_match:
                best_match.access_count += 1
                best_match.last_accessed = now
                logger.debug("Semantic cache hit: score=%.3f", best_score)
                return best_match.value
            return None

    def set(self, query: str, value: Any, **params) -> None:
        """Set value in semantic cache."""
        embedding = self._get_embedding(query)
        with self._lock:
            if len(self._cache) >= self.max_size:
                self._cache.sort(key=lambda e: e.last_accessed)
                self._cache.pop(0)
            entry = CacheEntry(
                key=hashlib.sha256(query.encode()).hexdigest()[:16],
                value=value,
                created_at=time.time(),
                embedding=embedding,
                metadata=params,
            )
            self._cache.append(entry)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "similarity_threshold": self.similarity_threshold,
                "ttl": self.ttl,
            }


class HybridCache:
    """Combined exact and semantic cache."""

    def __init__(
        self,
        exact_max_size: int = 1000,
        semantic_max_size: int = 500,
        similarity_threshold: float = 0.85,
        ttl: int = 3600,
    ):
        self.exact = ExactCache(max_size=exact_max_size, ttl=ttl)
        self.semantic = SemanticCache(
            max_size=semantic_max_size,
            similarity_threshold=similarity_threshold,
            ttl=ttl,
        )

    def get(self, query: str, **params) -> Optional[Any]:
        """Try exact cache first, then semantic."""
        result = self.exact.get(query, **params)
        if result is not None:
            return result
        return self.semantic.get(query, **params)

    def set(self, query: str, value: Any, **params) -> None:
        """Set in both caches."""
        self.exact.set(query, value, **params)
        self.semantic.set(query, value, **params)

    def invalidate(self, query: str, **params) -> bool:
        """Invalidate from exact cache."""
        return self.exact.invalidate(query, **params)

    def clear(self) -> None:
        """Clear both caches."""
        self.exact.clear()
        self.semantic.clear()

    def stats(self) -> Dict[str, Any]:
        """Get combined statistics."""
        return {
            "exact": self.exact.stats(),
            "semantic": self.semantic.stats(),
        }


query_cache = HybridCache()