"""Structured JSON logging with correlation IDs and secret redaction."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from src.config import get_settings
from src.context import current_principal, current_request_id

_configured = False

_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S+"), r"\1=***"),
    (re.compile(r"Bearer\s+\S+"), "Bearer ***"),
]


def _redact(text: str) -> str:
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _json_sink(message: Any) -> None:
    record = message.record
    payload = {
        "ts": record["time"].isoformat(),
        "level": record["level"].name,
        "module": record["extra"].get("module", record["name"]),
        "function": record["function"],
        "line": record["line"],
        "message": _redact(record["message"]),
        "request_id": current_request_id(),
        "principal": current_principal(),
    }
    sys.stderr.write(json.dumps(payload) + "\n")


def _text_sink(message: Any) -> None:
    record = message.record
    sys.stderr.write(
        f"{record['time'].strftime('%H:%M:%S.%f')[:-3]} | "
        f"{record['level'].name: <8} | "
        f"[{current_request_id()[:8]}] "
        f"{record['name']}:{record['line']} - "
        f"{_redact(record['message'])}\n"
    )


def setup_logger() -> None:
    global _configured
    if _configured:
        return
    s = get_settings()
    Path("logs").mkdir(exist_ok=True)

    logger.remove()
    sink = _json_sink if s.log_format == "json" else _text_sink
    logger.add(sink, level=s.log_level, colorize=False)
    logger.add(
        "logs/securedoc_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="14 days",
        level=s.log_level,
        enqueue=True,
        format="{message}",
    )
    _configured = True


def get_logger(name: str = "securedoc"):
    setup_logger()
    return logger.bind(module=name)
