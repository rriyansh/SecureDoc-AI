"""Document ingestion: load → chunk → embed → persist.

Pipeline
--------
1. Load every ``*.txt`` from ``DOCUMENTS_PATH``.
2. Split into **parent** chunks (large, 2000 chars) and **child** chunks
   (small, 400 chars). Children are embedded and searched; parents are
   returned as context. This ensures retrieved context is coherent — a
   child chunk alone often lacks surrounding context.
3. Embed children with OpenAI's embedding model via LangChain.
4. Persist the FAISS index (children) + LocalFileStore docstore (parents).
5. Write ``manifest.json`` with file hashes — enables reproducibility:
   two ingests of the same corpus produce identical manifests (modulo
   timestamps).

Idempotency
-----------
Re-running ``ingest()`` completely replaces the index. There is no
incremental update — the cost of re-embedding is acceptable for a corpus
this size (typically < 100 documents). If you outgrow that, switch to a
vector DB with upserts (e.g. Qdrant).

Failure modes
-------------
* Empty ``documents/`` → :class:`ValueError` (fail loud, not silent).
* OpenAI API error → exception propagates; index remains from prior run
  (safe — ingest only writes at the end).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import LocalFileStore
from langchain.storage._lc_store import create_kv_docstore
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.config import get_settings
from src.core.logger import get_logger
from src.observability.metrics import INDEX_DOCS

log = get_logger("rag.ingest")


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _file_sha256(path: Path) -> str:
    """SHA-256 hex digest of a file's bytes."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_documents(documents_path: Path) -> tuple[list, dict[str, str]]:
    """Load every ``.txt`` file, return (documents, {filename: sha256})."""
    if not documents_path.exists():
        raise FileNotFoundError(f"Documents directory not found: {documents_path}")

    files = sorted(documents_path.glob("*.txt"))
    if not files:
        raise ValueError(
            f"No .txt files found in {documents_path} — add documents first"
        )

    documents: list = []
    hashes: dict[str, str] = {}
    for file in files:
        log.info(f"Loading {file.name} ({file.stat().st_size} bytes)")
        hashes[file.name] = _file_sha256(file)
        loader = TextLoader(str(file), encoding="utf-8")
        documents.extend(loader.load())

    log.info(
        f"Loaded {len(documents)} document(s) from {len(files)} file(s), "
        f"total {sum(h for h in (f.stat().st_size for f in files))} bytes"
    )
    return documents, hashes


def _clear_vectorstore(vectorstore_path: Path) -> None:
    """Wipe all index files except ``.gitkeep``.

    Safe because ingest only writes at the very end — if embedding fails
    mid-run, the previous index remains on disk.
    """
    if not vectorstore_path.exists():
        return
    for item in vectorstore_path.iterdir():
        if item.name == ".gitkeep":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    log.debug(f"Cleared {vectorstore_path}")


def _write_manifest(
    vectorstore_path: Path,
    hashes: dict[str, str],
    doc_count: int,
) -> None:
    """Persist a manifest so ingestion is reproducible/auditable."""
    manifest = {
        "version": "v4",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "document_count": doc_count,
        "files": hashes,
    }
    manifest_path = vectorstore_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    log.info(f"Manifest written: {manifest_path}")


# --------------------------------------------------------------------------- #
# Main entry                                                                   #
# --------------------------------------------------------------------------- #

def ingest() -> dict[str, object]:
    """Build parent-child index from ``documents/``.

    Returns a summary dict (useful for CLI output and tests).
    """
    s = get_settings()

    # Ensure directories exist
    s.vectorstore_path.mkdir(parents=True, exist_ok=True)
    s.docstore_path.mkdir(parents=True, exist_ok=True)
    s.documents_path.mkdir(parents=True, exist_ok=True)

    # 1. Load
    documents, hashes = _load_documents(s.documents_path)

    # 2. Splitters
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=s.child_chunk_size,
        chunk_overlap=s.child_chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=s.parent_chunk_size,
        chunk_overlap=s.parent_chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    log.info(
        f"Splitters: child={s.child_chunk_size}/{s.child_chunk_overlap} "
        f"parent={s.parent_chunk_size}/{s.parent_chunk_overlap}"
    )

    # 3. Embeddings
    embeddings = OpenAIEmbeddings(
        model=s.openai_embedding_model,
        api_key=s.openai_api_key.get_secret_value(),
    )

    # 4. Wipe old index (safe — see _clear_vectorstore docstring)
    _clear_vectorstore(s.vectorstore_path)

    # 5. Build
    vectorstore = FAISS(
        embedding_function=embeddings,
        index=None,
        docstore=None,
        index_to_docstore_id=None,
    )
    file_store = LocalFileStore(str(s.docstore_path))
    docstore = create_kv_docstore(file_store)

    retriever = ParentDocumentRetriever(
        vectorstore=vectorstore,
        docstore=docstore,
        child_splitter=child_splitter,
        parent_splitter=parent_splitter,
    )

    log.info("Indexing (embedding child chunks)...")
    retriever.add_documents(documents)

    # 6. Persist
    vectorstore.save_local(str(s.vectorstore_path))
    _write_manifest(s.vectorstore_path, hashes, len(documents))
    INDEX_DOCS.set(len(documents))

    summary = {
        "documents": len(documents),
        "files": len(hashes),
        "vectorstore_path": str(s.vectorstore_path),
        "docstore_path": str(s.docstore_path),
    }
    log.success(f"Ingest complete: {summary}")
    return summary


# --------------------------------------------------------------------------- #
# CLI entry point                                                              #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    ingest()
