"""Document ingestion with Parent-Child chunking."""

from __future__ import annotations

import shutil

from langchain.storage import LocalFileStore
from langchain.storage._lc_store import create_kv_docstore
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.retrievers import ParentDocumentRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import get_settings
from src.logger import get_logger
from src.utils import ensure_dirs

log = get_logger("ingest")


def _load_documents(documents_path):
    docs = []
    if not documents_path.exists():
        raise FileNotFoundError(f"Documents path does not exist: {documents_path}")

    for file in sorted(documents_path.glob("*.txt")):
        log.info(f"Loading {file.name}")
        loader = TextLoader(str(file), encoding="utf-8")
        docs.extend(loader.load())

    if not docs:
        raise ValueError(f"No .txt files found in {documents_path}")

    log.info(f"Loaded {len(docs)} document(s)")
    return docs


def ingest() -> None:
    """Build the parent-child index and save artifacts to disk."""
    settings = get_settings()
    ensure_dirs(settings.vectorstore_path, settings.docstore_path)

    documents = _load_documents(settings.documents_path)

    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.child_chunk_size,
        chunk_overlap=settings.child_chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.parent_chunk_size,
        chunk_overlap=settings.parent_chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )

    # Wipe previous FAISS index to avoid stale data
    if settings.vectorstore_path.exists():
        for item in settings.vectorstore_path.iterdir():
            if item.name != ".gitkeep":
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

    vectorstore = FAISS(
        embedding_function=embeddings,
        index=None,
        docstore=None,
        index_to_docstore_id=None,
    )

    fs = LocalFileStore(str(settings.docstore_path))
    store = create_kv_docstore(fs)

    retriever = ParentDocumentRetriever(
        vectorstore=vectorstore,
        docstore=store,
        child_splitter=child_splitter,
        parent_splitter=parent_splitter,
    )

    log.info("Building parent-child index...")
    retriever.add_documents(documents)

    vectorstore.save_local(str(settings.vectorstore_path))
    log.info(f"Saved FAISS index to {settings.vectorstore_path}")
    log.info(f"Saved parent docstore to {settings.docstore_path}")
    log.success("Ingestion complete.")


if __name__ == "__main__":
    ingest()
