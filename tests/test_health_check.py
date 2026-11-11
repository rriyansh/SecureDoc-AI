"""Tests for health checks."""

from src.health_check import aggregate


def test_aggregate_returns_structure():
    result = aggregate()
    assert "healthy" in result
    assert "checks" in result
    assert isinstance(result["checks"], list)
