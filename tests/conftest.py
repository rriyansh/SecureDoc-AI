"""Pytest configuration and fixtures."""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def sample_text():
    return "SecureDoc AI company policy: all documents must be encrypted."


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_documents(temp_dir):
    """Create mock documents for testing."""
    docs = {
        "policy.txt": "All documents must be encrypted at rest and in transit.",
        "auth.txt": "Multi-factor authentication is required for all users.",
        "retention.txt": "Documents are retained for 7 years.",
    }
    for name, content in docs.items():
        (temp_dir / name).write_text(content)
    return temp_dir


@pytest.fixture
def api_key():
    """Generate a test API key."""
    from src.auth import api_key_manager
    return api_key_manager.create_key("Test Key", ["read", "write"])


@pytest.fixture
def jwt_token():
    """Generate a test JWT token."""
    from src.auth import jwt_manager
    return jwt_manager.create_token("test_user", ["read"])


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    # Clear caches
    from src.cache import query_cache
    query_cache.clear()

    # Clear rate limiters
    from src.rate_limiter import api_rate_limiter, query_rate_limiter
    api_rate_limiter._buckets.clear()
    query_rate_limiter._buckets.clear()

    yield

    # Cleanup after test
    query_cache.clear()
    api_rate_limiter._buckets.clear()
    query_rate_limiter._buckets.clear()