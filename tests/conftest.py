"""Shared fixtures."""

import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-please-change-me-to-32-bytes")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("API_KEYS", "test-api-key-1,test-api-key-2")
os.environ.setdefault("CACHE_ENCRYPT", "false")


@pytest.fixture(autouse=True)
def _reset_singletons():
    try:
        from src.cache import get_response_cache
        get_response_cache().clear()
    except Exception:
        pass
    yield
