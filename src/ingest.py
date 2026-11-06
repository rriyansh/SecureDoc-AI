"""Document ingestion pipeline."""

from pathlib import Path
from typing import List

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class DocumentChunk:
    def __init__(self, text: str, metadata: dict):
        self.text = text
        self.metadata = metadata


def load_documents(doc_dir: str = "documents") -> List[DocumentChunk]:
    """Load all .txt documents from a directory."""
    chunks: List[DocumentChunk] = []
    path = Path(doc_dir)
    if not path.exists():
        logger.warning("Document directory %s does not exist", doc_dir)
        return chunks

    for file_path in path.glob("*.txt"):
        try:
            text = file_path.read_text(encoding="utf-8")
            chunks.append(
                DocumentChunk(text=text, metadata={"source": str(file_path)})
            )
            logger.info("Loaded document %s", file_path.name)
        except OSError as exc:
            logger.error("Failed to read %s: %s", file_path, exc)

    return chunks


def chunk_text(text: str, chunk_size: int = None, chunk_overlap: int = None) -> List[str]:
    """Simple whitespace-aware text chunking."""
    chunk_size = chunk_size or config.chunk_size
    chunk_overlap = chunk_overlap or config.chunk_overlap
    words = text.split()
    chunks: List[str] = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - chunk_overlap
    return chunks


def ingest(doc_dir: str = "documents") -> List[DocumentChunk]:
    """Run the full ingestion flow: load + chunk documents."""
    documents = load_documents(doc_dir)
    total_chunks = 0
    for doc in documents:
        pieces = chunk_text(doc.text)
        total_chunks += len(pieces)
        logger.info("Document %s produced %d chunks", doc.metadata["source"], len(pieces))
    logger.info("Ingestion complete: %d documents, %d chunks", len(documents), total_chunks)
    return documents
