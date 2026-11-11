"""Tests for hybrid retriever."""

from unittest.mock import MagicMock, patch

import pytest

from src import hybrid_retriever


@pytest.fixture(autouse=True)
def _reset():
    hybrid_retriever.reset_retriever_cache()
    yield
    hybrid_retriever.reset_retriever_cache()


def test_missing_index(monkeypatch, tmp_path):
    from src.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("VECTORSTORE_PATH", str(tmp_path / "missing"))
    monkeypatch.setenv("DOCUMENTS_PATH", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        hybrid_retriever.build_hybrid_retriever()


def test_returns_ensemble(monkeypatch, tmp_path):
    from src.config import get_settings
    get_settings.cache_clear()
    docs = tmp_path / "docs"; docs.mkdir()
    (docs / "a.txt").write_text("hello", encoding="utf-8")
    vs = tmp_path / "vs"; vs.mkdir()
    (vs / "index.faiss").write_bytes(b"")
    monkeypatch.setenv("DOCUMENTS_PATH", str(docs))
    monkeypatch.setenv("VECTORSTORE_PATH", str(vs))

    with patch("src.hybrid_retriever.FAISS.load_local") as fa, \
         patch("src.hybrid_retriever.OpenAIEmbeddings"), \
         patch("src.hybrid_retriever.BM25Retriever.from_documents") as bm, \
         patch("src.hybrid_retriever.EnsembleRetriever") as en:
        fa.return_value = MagicMock()
        bm.return_value = MagicMock()
        en.return_value = MagicMock()
        assert hybrid_retriever.build_hybrid_retriever() is en.return_value
