"""AES-GCM encryption for cache values."""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.config import get_settings
from src.logger import get_logger

log = get_logger("crypto")


def _derive_key() -> bytes:
    raw = get_settings().cache_encryption_key.get_secret_value()
    if not raw:
        raise ValueError("CACHE_ENCRYPTION_KEY is not configured")
    # Ensure 32 bytes by hashing (allows any-length secret)
    import hashlib

    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt(plaintext: str) -> str:
    """Encrypt with AES-GCM. Returns base64(nonce + ciphertext)."""
    key = _derive_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt(blob: str) -> str:
    """Decrypt an AES-GCM base64 payload."""
    key = _derive_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(blob.encode("ascii"))
    nonce, ct = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
