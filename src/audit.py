"""Hash-chained, tamper-evident audit trail."""

from __future__ import annotations

import hashlib
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
_last_hash: dict[str, str] = {}  # per-day last hash


def _audit_path() -> Path:
    s = get_settings()
    s.audit_path.mkdir(parents=True, exist_ok=True)
    return s.audit_path / f"audit-{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"


def _chain_key(day: str) -> str:
    return day


def record(event: str, **fields: Any) -> None:
    s = get_settings()
    if not s.audit_enabled:
        return

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    for k, v in fields.items():
        payload[k] = truncate(v, s.audit_max_payload_chars) if isinstance(v, str) else v

    with _lock:
        if s.audit_chain_hash:
            prev = _last_hash.get(_chain_key(day), "0" * 64)
            serialized = json.dumps(payload, sort_keys=True, default=str)
            chain_hash = hashlib.sha256((prev + serialized).encode()).hexdigest()
            payload["prev_hash"] = prev
            payload["chain_hash"] = chain_hash
            _last_hash[_chain_key(day)] = chain_hash

        try:
            with _audit_path().open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        except Exception as exc:
            log.error(f"Audit write failed: {exc}")
