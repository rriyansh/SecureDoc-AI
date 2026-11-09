"""Shared fixtures."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-please-change-me-to-32-bytes")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("API_KEYS", "test-api-key-1,test-api-key-2")
os.environ.setdefault("VECTORSTORE_PATH", "./vectorstore")
os.environ.setdefault("DOCUMENTS_PATH", "./documents")


@pytest.fixture(autouse=True)
def _reset_singletons():
    try:
        from src.cache import get_response_cache
        get_response_cache().clear()
    except Exception:
        pass
    yield


@pytest.fixture
def mock_retriever():
    doc = MagicMock()
    doc.page_content = "Customer data retained for 3 years."
    r = MagicMock()
    r.invoke.return_value = [doc]
    return r
