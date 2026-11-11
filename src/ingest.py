"""Versioned document ingestion with parent-child chunking."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone

from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import LocalFileStore
from langchain.storage._lc_store import create_kv_docstore
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import get_settings
from src.logger import get_logger
from src.metrics import INDEX_DOCS
from src.utils import ensure_dirs, file_hash

log = get_logger("ingest")


def _load_documents(path):
    if not path.exists():
        raise FileNotFoundError(f"Documents path missing: {path}")
    docs = []
    hashes: dict[str, str] = {}
    for f in sorted(path.glob("*.txt")):
        log.info(f"Loading {f.name}")
        hashes[f.name] = file_hash(f)
        docs.extend(TextLoader(str(f), encoding="utf-8").load())
    if not docs:
        raise ValueError(f"No .txt files in {path}")
    return docs, hashes


def ingest() -> None:
    s = get_settings()
    ensure_dirs(s.vectorstore_path, s.docstore_path, s.documents_path)

    documents, hashes = _load_documents(s.documents_path)

    child_split = RecursiveCharacterTextSplitter(
        chunk_size=s.child_chunk_size,
        chunk_overlap=s.child_chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    parent_split = RecursiveCharacterTextSplitter(
        chunk_size=s.parent_chunk_size,
        chunk_overlap=s.parent_chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    embeddings = OpenAIEmbeddings(
        model=s.openai_embedding_model,
        api_key=s.openai_api_key.get_secret_value(),
    )

    if s.vectorstore_path.exists():
        for item in s.vectorstore_path.iterdir():
            if item.name == ".gitkeep":
                continue
            (shutil.rmtree(item) if item.is_dir() else item.unlink())

    vectorstore = FAISS(
        embedding_function=embeddings,
        index=None, docstore=None, index_to_docstore_id=None,
    )
    fs = LocalFileStore(str(s.docstore_path))
    store = create_kv_docstore(fs)

    retriever = ParentDocumentRetriever(
        vectorstore=vectorstore,
        docstore=store,
        child_splitter=child_split,
        parent_splitter=parent_split,
    )
    retriever.add_documents(documents)
    vectorstore.save_local(str(s.vectorstore_path))

    manifest = {
        "version": datetime.now(timezone.utc).isoformat(),
        "files": hashes,
        "count": len(documents),
    }
    (s.vectorstore_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    INDEX_DOCS.set(len(documents))
    log.success(f"Indexed {len(documents)} docs.")


if __name__ == "__main__":
    ingest()
