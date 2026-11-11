"""Hybrid retriever with adaptive k and reranking."""

from __future__ import annotations

from functools import lru_cache

from langchain.retrievers import BM25Retriever, EnsembleRetriever
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from src.config import get_settings
from src.logger import get_logger
from src.metrics import RETRIEVAL_DOCS
from src.reranker import rerank

log = get_logger("retriever")


def _load_raw(path):
    docs = []
    for f in sorted(path.glob("*.txt")):
        docs.extend(TextLoader(str(f), encoding="utf-8").load())
    if not docs:
        raise ValueError(f"No docs in {path}")
    return docs


@lru_cache(maxsize=1)
def build_hybrid_retriever() -> EnsembleRetriever:
    s = get_settings()
    log.info("Building hybrid retriever")

    if not (s.vectorstore_path / "index.faiss").exists():
        raise FileNotFoundError(
            f"FAISS index missing at {s.vectorstore_path}. Run `make ingest`."
        )

    embeddings = OpenAIEmbeddings(
        model=s.openai_embedding_model,
        api_key=s.openai_api_key.get_secret_value(),
    )
    vs = FAISS.load_local(
        str(s.vectorstore_path), embeddings, allow_dangerous_deserialization=True
    )
    vec = vs.as_retriever(search_kwargs={"k": s.retriever_top_k})

    bm25 = BM25Retriever.from_documents(_load_raw(s.documents_path))
    bm25.k = s.retriever_top_k

    ensemble = EnsembleRetriever(
        retrievers=[bm25, vec],
        weights=[s.bm25_weight, s.vector_weight],
    )
    log.success("Hybrid retriever ready.")
    return ensemble


def retrieve_and_rerank(query: str) -> list:
    s = get_settings()
    docs = build_hybrid_retriever().invoke(query)
    RETRIEVAL_DOCS.observe(len(docs))
    return rerank(query, docs, top_k=s.rerank_top_k)


def reset_retriever_cache() -> None:
    build_hybrid_retriever.cache_clear()
