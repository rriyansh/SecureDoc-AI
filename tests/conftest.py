"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_text():
    return "SecureDoc AI company policy: all documents must be encrypted."
