"""Shared utilities."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from src.logger import get_logger

log = get_logger("utils")


def file_hash(path: Path) -> str:
    """Return SHA-256 hash of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_text(text: str) -> str:
    """Collapse whitespace and normalise line endings."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_docs(docs: list) -> str:
    """Join retrieved document contents with separators."""
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


def ensure_dirs(*paths: Path) -> None:
    """Create directories if they do not exist."""
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
        log.debug(f"Ensured directory exists: {p}")
