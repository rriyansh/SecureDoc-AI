"""Shared utilities."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

from src.logger import get_logger

log = get_logger("utils")


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_docs(docs: Iterable[Any]) -> str:
    return "\n\n---\n\n".join(getattr(d, "page_content", str(d)) for d in docs)


def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def stable_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()


def mask_secret(secret: str, visible: int = 4) -> str:
    if len(secret) <= visible:
        return "***"
    return secret[:visible] + "***" + secret[-2:]
