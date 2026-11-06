"""Tests for the RAG pipeline."""

from src.rag_pipeline import SecureRAGPipeline


def test_query_no_results():
    pipeline = SecureRAGPipeline()
    answer = pipeline.query("completely unrelated topic xyz")
    assert "could not find relevant information" in answer
