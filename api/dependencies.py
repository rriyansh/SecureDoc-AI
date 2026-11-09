"""Reusable FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth import decode_access_token, verify_admin_key, verify_api_key
from src.rate_limiter import get_limiter

_bearer = HTTPBearer(auto_error=False)


def get_principal(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if x_api_key:
        return verify_api_key(x_api_key)
    if creds:
        payload = decode_access_token(creds.credentials)
        return f"jwt:{payload.get('sub', 'unknown')}"
    return verify_api_key(None)  # raises 401


def rate_limited(principal: str = Depends(get_principal)) -> str:
    get_limiter().check(principal)
    return principal


def get_admin(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> str:
    return verify_admin_key(x_admin_key)
