"""Hybrid (BM25 + Vector) retriever."""

from __future__ import annotations

from functools import lru_cache

from langchain.retrievers import BM25Retriever, EnsembleRetriever
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from src.config import get_settings
from src.logger import get_logger

log = get_logger("retriever")


def _load_raw_docs(documents_path):
    docs = []
    for file in sorted(documents_path.glob("*.txt")):
        docs.extend(TextLoader(str(file), encoding="utf-8").load())
    if not docs:
        raise ValueError(f"No documents found in {documents_path}")
    return docs


@lru_cache(maxsize=1)
def build_hybrid_retriever() -> EnsembleRetriever:
    """Build a cached hybrid retriever combining BM25 and FAISS."""
    settings = get_settings()
    log.info("Building hybrid retriever (BM25 + FAISS)")

    # Vector component
    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )
    if not (settings.vectorstore_path / "index.faiss").exists():
        raise FileNotFoundError(
            f"FAISS index not found at {settings.vectorstore_path}. "
            "Run `make ingest` first."
        )
    vectorstore = FAISS.load_local(
        str(settings.vectorstore_path),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    vector_retriever = vectorstore.as_retriever(
        search_kwargs={"k": settings.retriever_top_k}
    )

    # BM25 component
    raw_docs = _load_raw_docs(settings.documents_path)
    bm25_retriever = BM25Retriever.from_documents(raw_docs)
    bm25_retriever.k = settings.retriever_top_k

    ensemble = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[settings.bm25_weight, settings.vector_weight],
    )
    log.success("Hybrid retriever ready.")
    return ensemble


def reset_retriever_cache() -> None:
    """Clear the cached retriever (useful in tests after re-ingest)."""
    build_hybrid_retriever.cache_clear()
