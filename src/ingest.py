"""Document ingestion pipeline."""

import os
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from src.config import config
from src.logger import get_logger
from src.metrics import metrics
from src.audit import get_audit_logger, AuditEventType, AuditLevel
from src.security import sanitize_input, detect_pii, redact_pii

logger = get_logger(__name__)


@dataclass
class DocumentChunk:
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    chunk_id: str = ""

    def __post_init__(self):
        if not self.chunk_id:
            import uuid
            self.chunk_id = uuid.uuid4().hex[:12]


@dataclass
class IngestionResult:
    documents_processed: int = 0
    chunks_created: int = 0
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    pii_detected: bool = False


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
            # Sanitize and check for PII
            sanitized = sanitize_input(text)
            pii_findings = detect_pii(sanitized)
            if pii_findings:
                logger.warning("PII detected in %s: %d findings", file_path.name, len(pii_findings))
                sanitized = redact_pii(sanitized)

            chunks.append(
                DocumentChunk(
                    text=sanitized,
                    metadata={
                        "source": str(file_path),
                        "filename": file_path.name,
                        "size": len(text),
                        "pii_detected": len(pii_findings) > 0,
                    },
                )
            )
            logger.info("Loaded document %s (%d chars)", file_path.name, len(text))
        except OSError as exc:
            logger.error("Failed to read %s: %s", file_path, exc)

    return chunks


def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[DocumentChunk]:
    """Simple whitespace-aware text chunking with metadata preservation."""
    chunk_size = chunk_size or config.chunk_size
    chunk_overlap = chunk_overlap or config.chunk_overlap
    words = text.split()
    chunks: List[DocumentChunk] = []
    i = 0
    chunk_index = 0
    while i < len(words):
        chunk_words = words[i: i + chunk_size]
        chunk_text = " ".join(chunk_words)
        chunk_meta = (metadata or {}).copy()
        chunk_meta.update({
            "chunk_index": chunk_index,
            "start_word": i,
            "end_word": min(i + chunk_size, len(words)),
        })
        chunks.append(DocumentChunk(text=chunk_text, metadata=chunk_meta))
        chunk_index += 1
        i += chunk_size - chunk_overlap
    return chunks


def ingest(
    doc_dir: str = "documents",
    user_id: str = "system",
    request_id: str = "",
) -> IngestionResult:
    """Run the full ingestion flow: load + chunk documents."""
    start_time = time.time()
    audit = get_audit_logger()

    documents = load_documents(doc_dir)
    total_chunks = 0
    errors = []
    pii_detected = False

    for doc in documents:
        try:
            pieces = chunk_text(doc.text, metadata=doc.metadata)
            total_chunks += len(pieces)
            logger.info("Document %s produced %d chunks", doc.metadata.get("source", "unknown"), len(pieces))
            if doc.metadata.get("pii_detected"):
                pii_detected = True
        except Exception as exc:
            error_msg = f"Failed to chunk {doc.metadata.get('source', 'unknown')}: {exc}"
            logger.error(error_msg)
            errors.append(error_msg)

    duration_ms = (time.time() - start_time) * 1000

    result = IngestionResult(
        documents_processed=len(documents),
        chunks_created=total_chunks,
        duration_ms=duration_ms,
        errors=errors,
        pii_detected=pii_detected,
    )

    # Log to audit
    audit.log_ingestion(
        user_id=user_id,
        num_documents=len(documents),
        num_chunks=total_chunks,
        duration_ms=duration_ms,
        request_id=request_id,
        outcome="success" if not errors else "partial",
        error="; ".join(errors) if errors else None,
    )

    # Record metrics
    metrics.record_ingestion(len(documents), total_chunks, duration_ms / 1000)

    logger.info("Ingestion complete: %d documents, %d chunks in %.1fms", len(documents), total_chunks, duration_ms)
    return result


def build_index(
    doc_dir: str = "documents",
    collection_name: str = None,
    user_id: str = "system",
    request_id: str = "",
) -> IngestionResult:
    """Build vector index from documents (placeholder for actual vector store integration)."""
    logger.info("Building vector index from %s", doc_dir)
    result = ingest(doc_dir, user_id, request_id)

    # Placeholder for actual vector store indexing
    # This would connect to Qdrant and upsert embeddings
    logger.info("Index build placeholder - would index %d chunks to vector store", result.chunks_created)

    return result