"""Authentication: password hashing, API keys, JWT, revocation.

Design
------
* **Passwords** — bcrypt via passlib. Cost 12 (default) ≈ 250ms — good
  balance between security and login latency. Bcrypt truncates at 72 bytes;
  we enforce that on input.

* **API keys** — verification delegates to :class:`ApiKeyRepository` (Group B)
  so this module doesn't touch SQLAlchemy directly. The repository handles
  the SHA-256 + constant-time compare.

* **JWT** — HS256 signed with ``SECRET_KEY`` (64+ chars). Includes ``jti``
  (unique token ID), ``iss`` (issuer), ``aud`` (audience), ``exp`` (expiry).
  Verification checks all four.

* **Revocation** — JWT is stateless, so revocation requires state. We keep an
  in-process dict of ``jti → expires_at``. Cleaned up lazily on every
  ``revoke_token`` call. In a multi-replica deployment this needs Redis
  (documented limitation — see README).

Threat model addressed
----------------------
* Stolen API key → revocable via DB flag, immediate effect
* Stolen JWT → revocable via jti blocklist until natural expiry
* Timing attacks → constant-time compare everywhere
* Weak secrets → rejected at startup (see ``src.core.config``)
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.exceptions import AuthError
from src.core.logger import get_logger

log = get_logger("security.auth")


# --------------------------------------------------------------------------- #
# Password hashing                                                             #
# --------------------------------------------------------------------------- #

# bcrypt truncates at 72 bytes — passlib warns unless we pre-truncate.
# Schemes list allows future rotation: passlib picks the newest scheme for
# new hashes and accepts older ones for verification.
_pwd_ctx = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
    bcrypt__truncate_error=False,
)

_BCRYPT_MAX_BYTES = 72


def _prepare_password(password: str) -> bytes:
    """Encode and truncate the password to bcrypt's 72-byte limit.

    ``bcrypt`` silently truncates past 72 bytes. Truncating **before**
    encoding ensures we don't chop a multi-byte UTF-8 sequence in half
    (which produces different hashes on different platforms).
    """
    raw = password.encode("utf-8")
    if len(raw) <= _BCRYPT_MAX_BYTES:
        return raw
    # Slice by *bytes*, then decode with errors='ignore' to drop partial chars
    truncated = raw[:_BCRYPT_MAX_BYTES].decode("utf-8", errors="ignore")
    return truncated.encode("utf-8")


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (cost 12).

    Raises
    ------
    ValueError
        If password is empty or shorter than 8 chars. Weak-password policy
        lives here so all callers (seed script, admin UI, tests) share it.
    """
    if not isinstance(password, str):
        raise ValueError("password must be a string")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    if len(password) > 128:
        raise ValueError("password must be at most 128 characters")
    return _pwd_ctx.hash(_prepare_password(password))


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time verification of a password against a bcrypt hash."""
    if not password or not hashed:
        return False
    try:
        return _pwd_ctx.verify(_prepare_password(password), hashed)
    except (ValueError, TypeError):
        # Malformed hash → treat as failed auth, never raise
        log.warning("Password verify: malformed hash")
        return False


def needs_rehash(hashed: str) -> bool:
    """True if the stored hash uses outdated parameters and should be rotated."""
    try:
        return _pwd_ctx.needs_update(hashed)
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# API key verification (delegates to repository)                               #
# --------------------------------------------------------------------------- #

async def verify_api_key(
    raw: str | None,
    session: AsyncSession,
) -> tuple[str, str | None]:
    """Verify an API key against the database.

    Parameters
    ----------
    raw : str | None
        The raw key from the ``X-API-Key`` header.
    session : AsyncSession
        Database session (caller owns the transaction).

    Returns
    -------
    tuple[str, str | None]
        ``(principal, user_id)``. ``principal`` is an opaque, log-safe
        identifier like ``"key:abc123def456:id12345678"``.

    Raises
    ------
    HTTPException
        401 on any failure (missing, invalid, revoked, expired).
    """
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Lazy import — avoids circular import at module load
    from src.db.repositories.api_key import ApiKeyRepository

    repo = ApiKeyRepository(session)
    record = await repo.lookup_by_raw_key(raw)
    if record is None:
        log.warning(f"Invalid API key attempt (prefix={raw[:4]!r}***)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    await repo.touch_last_used(record.id)
    principal = f"key:{record.prefix}:{record.id[:8]}"
    log.info(f"API key auth OK: principal={principal} user={record.user_id[:8]}")
    return principal, record.user_id


# --------------------------------------------------------------------------- #
# JWT                                                                          #
# --------------------------------------------------------------------------- #

def _encode_jwt(payload: dict[str, Any]) -> str:
    s = get_settings()
    return jwt.encode(
        payload,
        s.secret_key.get_secret_value(),
        algorithm=s.jwt_algorithm,
    )


def _decode_jwt(token: str) -> dict[str, Any]:
    s = get_settings()
    return jwt.decode(
        token,
        s.secret_key.get_secret_value(),
        algorithms=[s.jwt_algorithm],
        issuer=s.jwt_issuer,
        audience=s.jwt_audience,
    )


def create_access_token(
    subject: str,
    *,
    extra: dict[str, Any] | None = None,
    expires_in_minutes: int | None = None,
) -> str:
    """Issue a signed JWT for ``subject`` (usually the user UUID).

    Parameters
    ----------
    subject : str
        ``sub`` claim — the user ID (or API key principal).
    extra : dict | None
        Additional non-sensitive claims (e.g. ``{"email": ..., "admin": ...}``).
    expires_in_minutes : int | None
        Override ``JWT_EXPIRE_MINUTES`` for short-lived tokens.
    """
    s = get_settings()
    now = datetime.now(timezone.utc)
    ttl = expires_in_minutes or s.jwt_expire_minutes

    payload: dict[str, Any] = {
        "sub": subject,
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)

    token = _encode_jwt(payload)
    log.debug(f"JWT issued for sub={subject[:8]} (ttl={ttl}min)")
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Checks signature, issuer, audience, expiry, revocation."""
    if not token:
        raise AuthError("Missing token")

    try:
        payload = _decode_jwt(token)
    except JWTError as exc:
        log.warning(f"JWT decode failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    jti = payload.get("jti")
    if jti:
        with _revoked_lock:
            if jti in _revoked:
                log.warning(f"JWT rejected (revoked): jti={jti[:8]}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    return payload


# --------------------------------------------------------------------------- #
# Revocation (in-process)                                                      #
# --------------------------------------------------------------------------- #

_revoked: dict[str, float] = {}
_revoked_lock = threading.Lock()

# Opportunistic cleanup of stale entries once every N calls.
_REVOCATION_CLEANUP_EVERY = 500
_revocation_ops = 0


def _cleanup_revoked() -> None:
    """Drop entries past their natural expiry — they're dead weight."""
    now = time.monotonic()
    with _revoked_lock:
        stale = [jti for jti, exp in _revoked.items() if exp <= now]
        for jti in stale:
            del _revoked[jti]
    if stale:
        log.debug(f"Revocation cleanup: dropped {len(stale)} expired entries")


def revoke_token(jti: str, ttl_seconds: int = 3600) -> None:
    """Add a ``jti`` to the revocation blocklist.

    ``ttl_seconds`` should match the token's remaining lifetime so the entry
    can be dropped after natural expiry.
    """
    global _revocation_ops
    if not jti:
        raise ValueError("jti required")

    with _revoked_lock:
        _revoked[jti] = time.monotonic() + ttl_seconds
        _revocation_ops += 1

    log.info(f"JWT revoked: jti={jti[:8]} (ttl={ttl_seconds}s)")

    if _revocation_ops >= _REVOCATION_CLEANUP_EVERY:
        _revocation_ops = 0
        _cleanup_revoked()


def revoke_all_tokens_for_user(user_id: str) -> int:
    """Best-effort revoke-all for a user.

    JWTs are stateless — we can't enumerate live tokens. This function exists
    as an explicit hook for a future shared-state implementation (Redis-backed
    revocation store). Today it returns 0 with a warning, which is the
    honest behavior: rotate the user's password and API keys instead.
    """
    log.warning(
        f"revoke_all_tokens_for_user(user={user_id[:8]}) is a no-op in "
        f"single-process mode — rotate the user's credentials instead"
    )
    return 0


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def hash_chain_key(prev_hash: str | None, payload: str) -> str:
    """SHA-256 hash chaining: ``sha256(prev_hash || payload)``.

    Used by the audit trail (``src.db.repositories.audit``) and exports here
    so other modules don't need to import hashlib directly.
    """
    prefix = prev_hash or ("0" * 64)
    return hashlib.sha256((prefix + payload).encode("utf-8")).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison — prevents timing side-channels."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
