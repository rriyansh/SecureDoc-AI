"""Tests for deduplicator."""

from src.dedup import Deduplicator


def test_first_call_not_duplicate():
    d = Deduplicator(window_seconds=60)
    assert not d.is_duplicate("a", "b")


def test_second_call_duplicate():
    d = Deduplicator(window_seconds=60)
    d.is_duplicate("a", "b")
    assert d.is_duplicate("a", "b")


def test_different_keys():
    d = Deduplicator(window_seconds=60)
    d.is_duplicate("a", "b")
    assert not d.is_duplicate("a", "c")
