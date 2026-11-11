"""HMAC-based request signing (defense-in-depth)."""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import HTTPException, status

from src.config import get_settings
from src.logger import get_logger

log = get_logger("signer")


def _sign(method: str, path: str, body: bytes, ts: str) -> str:
    s = get_settings()
    msg = f"{method}|{path}|{ts}|".encode() + body
    return hmac.new(
        s.request_signing_secret.get_secret_value().encode(),
        msg,
        hashlib.sha256,
    ).hexdigest()


def verify_signature(
    method: str,
    path: str,
    body: bytes,
    timestamp: str | None,
    signature: str | None,
) -> None:
    s = get_settings()
    if not s.request_signing_enabled:
        return

    if not timestamp or not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing request signature",
        )

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid timestamp")

    if abs(time.time() - ts_int) > s.request_signing_window_seconds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature expired",
        )

    expected = _sign(method, path, body, timestamp)
    if not hmac.compare_digest(expected, signature):
        log.warning("Signature mismatch")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad signature")
