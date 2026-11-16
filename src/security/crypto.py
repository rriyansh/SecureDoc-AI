"""Symmetric encryption and HMAC primitives.

Used by
-------
* ``src.cache.memory`` / ``src.cache.redis_cache`` — encrypt cached answers
  at rest with AES-GCM so a Redis dump can't leak query responses.
* ``src.security.request_signer`` — HMAC-SHA256 request signatures.

Why AES-GCM (not AES-CBC)
-------------------------
GCM is **authenticated**: it detects tampering. CBC would require a separate
MAC and careful padding handling. GCM is one operation, no padding, and
produces a tag that decrypt verifies. Cost is negligible for cache-sized
payloads (< 10 KB).

Why 12-byte nonce
-----------------
96 bits is the standard GCM nonce. Random nonces at this size are safe up
to ~2^32 messages per key (birthday bound is ~2^48 messages) — vastly more
than any cache we'll ever serve per key rotation.

Why derive keys
---------------
The raw env var is human-generated; we SHA-256 it into a proper 32-byte
AES key. This means any string ≥ 32 chars produces a valid key, and the
same raw string always produces the same key (deterministic — required
since we don't store derived keys).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.core.config import get_settings
from src.core.exceptions import AppError
from src.core.logger import get_logger

log = get_logger("security.crypto")


# --------------------------------------------------------------------------- #
# Errors                                                                       #
# --------------------------------------------------------------------------- #

class DecryptionError(AppError):
    """Raised when ciphertext cannot be decrypted (tamper/corruption)."""

    code = "decryption_error"
    status_code = 500


# --------------------------------------------------------------------------- #
# Key derivation                                                               #
# --------------------------------------------------------------------------- #

_NONCE_LEN = 12
_AES_KEY_LEN = 32  # 256-bit


def safe_key_derive(raw: str) -> bytes:
    """Derive a 32-byte AES key from a raw string via SHA-256.

    Deterministic: same input → same key. This is safe because the raw
    string already carries at least 32 chars of entropy (validated at
    startup in ``src.core.config``).
    """
    if not raw:
        raise ValueError("cannot derive key from empty string")
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _cache_key() -> bytes:
    """Return the derived cache encryption key from settings."""
    raw = get_settings().cache_encryption_key.get_secret_value()
    if not raw:
        raise AppError(
            "Cache encryption key not configured",
            code="missing_encryption_key",
            status_code=500,
        )
    return safe_key_derive(raw)


# --------------------------------------------------------------------------- #
# AES-GCM                                                                      #
# --------------------------------------------------------------------------- #

def encrypt(plaintext: str) -> str:
    """Encrypt a string with AES-GCM.

    Output format: ``base64(nonce || ciphertext_with_tag)``.

    Raises
    ------
    AppError
        If the encryption key is not configured.
    """
    if not isinstance(plaintext, str):
        raise TypeError("plaintext must be str")

    key = _cache_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt(blob: str) -> str:
    """Decrypt a payload produced by :func:`encrypt`.

    Raises
    ------
    DecryptionError
        If the blob is malformed, truncated, or was tampered with.
    """
    if not isinstance(blob, str):
        raise TypeError("blob must be str")

    try:
        raw = base64.b64decode(blob.encode("ascii"), validate=True)
    except Exception as exc:
        raise DecryptionError("Invalid base64 in ciphertext") from exc

    if len(raw) < _NONCE_LEN + 16:  # nonce + minimum GCM tag
        raise DecryptionError("Ciphertext too short")

    key = _cache_key()
    aesgcm = AESGCM(key)
    nonce, ciphertext = raw[:_NONCE_LEN], raw[_NONCE_LEN:]

    try:
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        log.warning("AES-GCM auth tag mismatch — possible tampering")
        raise DecryptionError("Decryption failed: authentication tag mismatch") from exc
    except Exception as exc:
        raise DecryptionError(f"Decryption failed: {type(exc).__name__}") from exc

    return plaintext_bytes.decode("utf-8")


# --------------------------------------------------------------------------- #
# HMAC                                                                         #
# --------------------------------------------------------------------------- #

def hmac_sha256_hex(key: str | bytes, message: bytes | str) -> str:
    """HMAC-SHA256 hex digest.

    Accepts str or bytes for both args to be convenient in tests and request
    signing. If ``message`` is str it's UTF-8 encoded.
    """
    key_bytes = key.encode("utf-8") if isinstance(key, str) else key
    msg_bytes = message.encode("utf-8") if isinstance(message, str) else message
    return hmac.new(key_bytes, msg_bytes, hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------- #
# Constant-time compare (aliased here for crypto-adjacent callers)             #
# --------------------------------------------------------------------------- #

def constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison.

    Both inputs are UTF-8 encoded before comparison so Unicode strings
    compare byte-for-byte (matching how they'd hit the wire).
    """
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
