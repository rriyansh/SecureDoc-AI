"""Append-only JSONL audit trail."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.logger import get_logger
from src.utils import truncate

log = get_logger("audit")
_lock = threading.Lock()


def _audit_path() -> Path:
    s = get_settings()
    s.audit_path.mkdir(parents=True, exist_ok=True)
    return s.audit_path / f"audit-{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"


def record(event: str, **fields: Any) -> None:
    s = get_settings()
    if not s.audit_enabled:
        return
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    for k, v in fields.items():
        payload[k] = truncate(v, s.audit_max_payload_chars) if isinstance(v, str) else v
    try:
        with _lock, _audit_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:
        log.error(f"Audit write failed: {exc}")
