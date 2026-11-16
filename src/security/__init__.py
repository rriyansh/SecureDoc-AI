"""SecureDoc AI v4 — Security layer.

Primitives for authentication, cryptography, input sanitization, and PII
handling. Every function here is written defensively with constant-time
comparison where it matters, and validated at the boundary.

Dependency direction
--------------------
- ``src.security`` may import from ``src.core`` (config, logging, exceptions).
- ``src.security`` MAY import from ``src.db.repositories`` (for API key
  lookup) — but ONLY inside functions, never at module top-level. This
  avoids circular imports during ORM model registration.
- ``src.security`` MUST NOT import from ``src.cache``, ``src.rag``,
  ``src.resilience``, or ``api/``.

Public API
----------
>>> from src.security import scan, redact_pii, hash_password, verify_password
>>> from src.security import create_access_token, decode_access_token
>>> from src.security import encrypt, decrypt
"""

from __future__ import annotations

# --- Auth ---
from src.security.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_chain_key,
    revoke_all_tokens_for_user,
    revoke_token,
    verify_api_key,
    verify_password,
)

# --- Crypto ---
from src.security.crypto import (
    constant_time_compare,
    decrypt,
    encrypt,
    hmac_sha256_hex,
    safe_key_derive,
)

# --- PII ---
from src.security.pii import (
    PIIType,
    detect_pii,
    redact_pii,
)

# --- Sanitize ---
from src.security.sanitize import (
    ScanResult,
    clamp,
    detect_encoded,
    detect_injection,
    escape_html,
    normalize_unicode,
    scan,
    strip_hidden,
)

# --- Request signing ---
from src.security.request_signer import (
    sign_request,
    verify_signature,
)

__all__ = [
    # Auth
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "verify_api_key",
    "revoke_token",
    "revoke_all_tokens_for_user",
    "hash_chain_key",
    # Crypto
    "encrypt",
    "decrypt",
    "hmac_sha256_hex",
    "constant_time_compare",
    "safe_key_derive",
    # PII
    "PIIType",
    "detect_pii",
    "redact_pii",
    # Sanitize
    "ScanResult",
    "scan",
    "normalize_unicode",
    "strip_hidden",
    "detect_injection",
    "detect_encoded",
    "clamp",
    "escape_html",
    # Request signing
    "sign_request",
    "verify_signature",
]
