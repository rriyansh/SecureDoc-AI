"""Tests for the hybrid retriever."""

from src.hybrid_retriever import HybridRetriever, RetrievalResult


def test_retriever_returns_empty():
    retriever = HybridRetriever()
    results = retriever.retrieve("anything")
    assert results == []


def test_rerank_orders_by_score():
    retriever = HybridRetriever(top_k=2)
    results = [
        RetrievalResult(text="low", score=0.1),
        RetrievalResult(text="high", score=0.9),
        RetrievalResult(text="mid", score=0.5),
    ]
    ranked = retriever.rerank("q", results)
    assert [r.text for r in ranked] == ["high", "mid"]
