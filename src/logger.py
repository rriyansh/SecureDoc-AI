"""Structured logging with automatic secret redaction."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from src.config import get_settings

_configured = False

_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S+"), r"\1=***"),
]


def _redact_filter(record: dict[str, Any]) -> bool:
    msg = record.get("message")
    if isinstance(msg, str):
        for pattern, repl in _SECRET_PATTERNS:
            msg = pattern.sub(repl, msg)
        record["message"] = msg
    return True


def setup_logger() -> None:
    global _configured
    if _configured:
        return
    s = get_settings()
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=s.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
        filter=_redact_filter,
    )
    logger.add(
        log_dir / "securedoc_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="14 days",
        level=s.log_level,
        enqueue=True,
        filter=_redact_filter,
    )
    _configured = True


def get_logger(name: str = "securedoc"):
    setup_logger()
    return logger.bind(module=name)
