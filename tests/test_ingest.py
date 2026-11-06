"""Tests for the ingestion module."""

from src.ingest import chunk_text


def test_chunk_text():
    text = "a b c d e f g h i j"
    chunks = chunk_text(text, chunk_size=4, chunk_overlap=1)
    assert len(chunks) == 3
    assert chunks[0] == "a b c d"
    assert chunks[1] == "d e f g"
    assert chunks[2] == "g h i j"


def test_chunk_text_short():
    text = "hello world"
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)
    assert chunks == ["hello world"]
