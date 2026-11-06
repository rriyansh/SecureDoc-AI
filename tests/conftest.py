"""Shared pytest fixtures."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure fake key before settings import
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")


@pytest.fixture(scope="session")
def fake_documents(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("documents")
    (d / "sample.txt").write_text(
        "Company data retention policy: customer data is retained for 3 years. "
        "Access is restricted to authorized personnel.",
        encoding="utf-8",
    )
    return d


@pytest.fixture
def mock_retriever():
    """Return a retriever that yields one fake document."""
    doc = MagicMock()
    doc.page_content = "Customer data retained for 3 years."
    retriever = MagicMock()
    retriever.invoke.return_value = [doc]
    retriever.get_relevant_documents.return_value = [doc]
    return retriever


@pytest.fixture
def mock_llm_chain():
    """Return a chain stub that echoes a canned answer."""
    chain = MagicMock()
    chain.invoke.return_value = "Customer data is retained for 3 years."
    return chain
