"""Tests for the hybrid retriever construction."""

from unittest.mock import MagicMock, patch

import pytest

from src import hybrid_retriever


@pytest.fixture(autouse=True)
def clear_cache():
    hybrid_retriever.reset_retriever_cache()
    yield
    hybrid_retriever.reset_retriever_cache()


def test_build_hybrid_retriever_missing_index(monkeypatch, tmp_path):
    from src.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("VECTORSTORE_PATH", str(tmp_path / "missing"))
    monkeypatch.setenv("DOCUMENTS_PATH", str(tmp_path))

    with pytest.raises(FileNotFoundError):
        hybrid_retriever.build_hybrid_retriever()


def test_build_hybrid_retriever_returns_ensemble(monkeypatch, tmp_path):
    from src.config import get_settings

    get_settings.cache_clear()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("hello world", encoding="utf-8")
    vs = tmp_path / "vs"
    vs.mkdir()
    (vs / "index.faiss").write_bytes(b"")

    monkeypatch.setenv("DOCUMENTS_PATH", str(docs))
    monkeypatch.setenv("VECTORSTORE_PATH", str(vs))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    with patch(
        "src.hybrid_retriever.FAISS.load_local"
    ) as mock_faiss, patch(
        "src.hybrid_retriever.OpenAIEmbeddings"
    ) as mock_emb, patch(
        "src.hybrid_retriever.BM25Retriever.from_documents"
    ) as mock_bm25, patch(
        "src.hybrid_retriever.EnsembleRetriever"
    ) as mock_ens:
        mock_faiss.return_value = MagicMock()
        mock_emb.return_value = MagicMock()
        mock_bm25.return_value = MagicMock()
        mock_ens.return_value = MagicMock()

        result = hybrid_retriever.build_hybrid_retriever()
        assert result is mock_ens.return_value
        mock_ens.assert_called_once()
