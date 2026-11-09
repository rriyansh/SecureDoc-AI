"""API-key and JWT authentication."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config import get_settings
from src.logger import get_logger

log = get_logger("auth")
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _principal_from_key(key: str) -> str:
    return f"key:{hashlib.sha256(key.encode()).hexdigest()[:12]}"


def verify_api_key(candidate: str | None) -> str:
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    for key in get_settings().api_key_set:
        if hmac.compare_digest(candidate, key):
            return _principal_from_key(candidate)
    log.warning(f"Invalid key prefix={candidate[:4]}***")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )


def verify_admin_key(candidate: str | None) -> str:
    s = get_settings()
    if not candidate or not hmac.compare_digest(candidate, s.admin_api_key.get_secret_value()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin key required")
    return "admin"


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.jwt_expire_minutes)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.jwt_secret.get_secret_value(), algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret.get_secret_value(), algorithms=[s.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def hash_secret(secret: str) -> str:
    return _pwd.hash(secret)


def verify_secret(secret: str, hashed: str) -> bool:
    try:
        return _pwd.verify(secret, hashed)
    except ValueError:
        return False
