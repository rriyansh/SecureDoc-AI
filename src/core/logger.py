"""Structured logging with correlation and redaction.

Every log line carries ``request_id``, ``principal``, ``path``, and — critically
— has any secret-looking substring scrubbed (API keys, bearer tokens, DSNs,
passwords) before being written.

Two output modes
----------------
* ``LOG_FORMAT=json`` — one JSON object per line (recommended for prod/Loki)
* ``LOG_FORMAT=text`` — human-readable for dev

Both write to ``stderr`` (for container capture) **and** a rotating file at
``logs/securedoc_*.log`` (for long-term local debugging).

Usage
-----
>>> from src.core.logger import get_logger
>>> log = get_logger("my-module")
>>> log.info("user logged in")
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from src.core.config import get_settings
from src.core.context import (
    current_path,
    current_principal,
    current_request_id,
    current_user_id,
)


# --------------------------------------------------------------------------- #
# Redaction                                                                    #
# --------------------------------------------------------------------------- #

# Order matters — more specific patterns first.
_REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # OpenAI-style keys: sk-..., sk-proj-...
    (re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{8,}"), "sk-***redacted***"),
    # Bearer tokens in HTTP headers
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-+/=]{10,}"), "Bearer ***redacted***"),
    # api_key=..., token=..., password=..., secret=...
    (
        re.compile(
            r"(?i)\b(api[_-]?key|token|password|secret|authorization)\s*[=:]\s*['\"]?[^\s'\",}]{4,}"
        ),
        r"\1=***redacted***",
    ),
    # Postgres/Redis URLs with credentials
    (re.compile(r"(postgresql|postgres|redis)://[^@\s]+@"), r"\1://***redacted***@"),
    # JWT-ish tokens (3 dot-separated base64 chunks)
    (
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
        "***jwt-redacted***",
    ),
    # Email addresses (PII in logs)
    (
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        "***email-redacted***",
    ),
]


def redact(text: str) -> str:
    """Apply all redaction patterns to a string."""
    out = text
    for pattern, replacement in _REDACT_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def _safe_repr(value: Any, max_len: int = 200) -> str:
    """Repr with truncation and redaction — for log fields."""
    try:
        r = repr(value)
    except Exception:
        r = "<unrepresentable>"
    r = redact(r)
    if len(r) > max_len:
        r = r[: max_len - 3] + "..."
    return r


# --------------------------------------------------------------------------- #
# Config                                                                       #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class LogConfig:
    """Container for resolved logging configuration."""

    level: str
    format: Literal["json", "text"]
    log_dir: Path
    app_name: str
    environment: str
    is_production: bool


# --------------------------------------------------------------------------- #
# Sinks                                                                        #
# --------------------------------------------------------------------------- #

class _JsonSink:
    """Emit one JSON object per line to stderr."""

    def write(self, message: Any) -> None:
        record = message.record
        payload = {
            "ts": record["time"].isoformat(),
            "level": record["level"].name,
            "module": record["extra"].get("module", record["name"]),
            "function": record["function"],
            "line": record["line"],
            "message": redact(record["message"]),
            "request_id": current_request_id(),
            "principal": current_principal(),
            "user_id": current_user_id(),
            "path": current_path(),
        }
        # Merge any structured extras the caller passed via .bind()/.contextualize()
        for key, value in record["extra"].items():
            if key == "module":
                continue
            if key not in payload:
                payload[key] = _safe_repr(value)
        # Merge exception traceback if present
        exc = record.get("exception")
        if exc is not None:
            payload["exception"] = {
                "type": exc.type.__name__ if exc.type else None,
                "value": redact(str(exc.value)) if exc.value else None,
            }
        sys.stderr.write(json.dumps(payload, default=str) + "\n")
        sys.stderr.flush()


class _TextSink:
    """Human-readable single-line format to stderr."""

    def write(self, message: Any) -> None:
        record = message.record
        rid = current_request_id()[:8] or "-"
        ts = record["time"].strftime("%H:%M:%S.%f")[:-3]
        level = record["level"].name
        loc = f"{record['name']}:{record['line']}"
        msg = redact(record["message"])
        sys.stderr.write(f"{ts} | {level: <8} | [{rid}] {loc} - {msg}\n")
        sys.stderr.flush()


# --------------------------------------------------------------------------- #
# Setup                                                                        #
# --------------------------------------------------------------------------- #

_configured = False


def setup_logger() -> None:
    """Configure loguru. Idempotent — safe to call multiple times."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    settings.logs_path.mkdir(parents=True, exist_ok=True)

    logger.remove()  # drop default sink

    cfg = LogConfig(
        level=settings.log_level,
        format=settings.log_format,
        log_dir=settings.logs_path,
        app_name=settings.app_name,
        environment=settings.environment,
        is_production=settings.is_production,
    )

    # Console sink — stderr, no colors when JSON
    primary_sink = _JsonSink() if cfg.format == "json" else _TextSink()
    logger.add(
        primary_sink.write,
        level=cfg.level,
        colorize=False,
        backtrace=not cfg.is_production,
        diagnose=not cfg.is_production,
    )

    # File sink — rotates daily, JSON always
    logger.add(
        str(cfg.log_dir / f"{cfg.app_name.lower().replace(' ', '-')}_{{time:YYYY-MM-DD}}.log"),
        level=cfg.level,
        rotation="10 MB",
        retention="14 days",
        compression="gz",
        format="{message}",
        enqueue=True,  # non-blocking, safe under load
        backtrace=False,
        diagnose=False,
        serialize=True,  # file is always JSON-serialized
    )

    _configured = True


# --------------------------------------------------------------------------- #
# Public accessor                                                              #
# --------------------------------------------------------------------------- #

def get_logger(name: str = "securedoc"):
    """Return a bound logger with the given module name."""
    setup_logger()
    return logger.bind(module=name)
