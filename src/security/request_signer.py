"""HMAC request signing — optional defense-in-depth.

Why
---
Even with API keys, an attacker who obtains a key can replay captured
requests or tamper with bodies in-flight (e.g. if a proxy or CDN is
compromised). Request signing adds a second factor that:

1. **Binds the request** to method + path + timestamp + body — any change
   invalidates the signature.
2. **Prevents replay** via a timestamp window (default 300s).
3. **Is transparent** to the HTTP layer — no changes to auth headers.

Protocol
--------
Client computes::

    sig = HMAC-SHA256(
        key = REQUEST_SIGNING_SECRET,
        msg = f"{METHOD}|{PATH}|{TIMESTAMP}|{BODY}"
    ).hexdigest()

Headers::

    X-Timestamp: 1735689600          (UNIX seconds)
    X-Signature: 8f3a7e...           (hex digest)

Server verifies:
1. Both headers present (else 401)
2. Timestamp within ±window (else 401)
3. Recomputed signature matches (constant-time, else 401)

State
-----
**Disabled by default** (``REQUEST_SIGNING_ENABLED=false``). Opt-in because
it requires every client to change. Enable only when you have a controlled
client population.
"""

from __future__ import annotations

import time

from fastapi import HTTPException, status

from src.core.config import get_settings
from src.core.logger import get_logger
from src.security.crypto import constant_time_compare, hmac_sha256_hex

log = get_logger("security.signer")


# --------------------------------------------------------------------------- #
# Signing (used by tests and internal SDKs)                                    #
# --------------------------------------------------------------------------- #

def _canonical_message(method: str, path: str, timestamp: str, body: bytes) -> bytes:
    """Build the exact bytes that both sides will MAC.

    The separators are literal ``|`` characters — chosen because they cannot
    appear in ``METHOD`` (uppercase letters) or a URL ``path`` (percent-
    encoded), and ``timestamp`` is digits. Body is raw bytes appended last
    so nothing after it can confuse the parser.
    """
    return f"{method.upper()}|{path}|{timestamp}|".encode("utf-8") + body


def _compute_signature(method: str, path: str, timestamp: str, body: bytes) -> str:
    secret = get_settings().request_signing_secret.get_secret_value()
    if not secret:
        raise RuntimeError("REQUEST_SIGNING_SECRET not configured")
    return hmac_sha256_hex(secret, _canonical_message(method, path, timestamp, body))


def sign_request(
    method: str,
    path: str,
    body: bytes = b"",
    *,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Return the headers needed to sign a request (for client SDKs / tests).

    Example
    -------
    >>> headers = sign_request("POST", "/api/v1/query", b'{"q":"hi"}')
    >>> headers.keys()
    dict_keys(['X-Timestamp', 'X-Signature'])
    """
    ts = str(timestamp if timestamp is not None else int(time.time()))
    sig = _compute_signature(method, path, ts, body)
    return {"X-Timestamp": ts, "X-Signature": sig}


# --------------------------------------------------------------------------- #
# Verification (server-side)                                                   #
# --------------------------------------------------------------------------- #

def verify_signature(
    method: str,
    path: str,
    body: bytes,
    timestamp: str | None,
    signature: str | None,
) -> None:
    """Verify HMAC request signature.

    When signing is disabled this is a no-op (fast path — one config read).

    Raises
    ------
    HTTPException 401
        If signing is enabled and verification fails.
    """
    s = get_settings()
    if not s.request_signing_enabled:
        return  # No-op — most deployments run with signing disabled

    # 1. Presence
    if not timestamp or not signature:
        log.warning(f"Request signing: missing headers (path={path})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing request signature headers",
            headers={"WWW-Authenticate": "HMAC"},
        )

    # 2. Timestamp parse + window
    try:
        ts_int = int(timestamp)
    except ValueError as exc:
        log.warning(f"Request signing: invalid timestamp {timestamp!r}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid timestamp",
        ) from exc

    now = int(time.time())
    skew = abs(now - ts_int)
    if skew > s.request_signing_window_seconds:
        log.warning(
            f"Request signing: timestamp skew {skew}s exceeds "
            f"window {s.request_signing_window_seconds}s"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Signature expired (skew={skew}s)",
        )

    # 3. Recompute + constant-time compare
    try:
        expected = _compute_signature(method, path, timestamp, body)
    except RuntimeError as exc:
        # Secret misconfigured — this is a server bug, not client's fault
        log.error(f"Request signing misconfigured: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signature verification unavailable",
        ) from exc

    if not constant_time_compare(expected, signature):
        log.warning(
            f"Request signing: signature mismatch "
            f"(method={method} path={path} ts={timestamp})"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    log.debug(f"Request signature verified (method={method} path={path})")
