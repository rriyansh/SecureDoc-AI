"""Reusable FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.anomaly import check as anomaly_check
from src.auth import decode_access_token, verify_admin_key, verify_api_key
from src.context import current_request_id, set_request_context
from src.rate_limiter import get_limiter

_bearer = HTTPBearer(auto_error=False)


def get_principal(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if x_api_key:
        p = verify_api_key(x_api_key)
    elif creds:
        payload = decode_access_token(creds.credentials)
        p = f"jwt:{payload.get('sub', 'unknown')}"
    else:
        p = verify_api_key(None)
    set_request_context(current_request_id(), p)
    return p


def rate_limited(principal: str = Depends(get_principal)) -> str:
    get_limiter().check(principal)
    return principal


def anomaly_checked(principal: str = Depends(rate_limited)) -> str:
    anomaly_check(principal, payload="")
    return principal


def get_admin(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> str:
    return verify_admin_key(x_admin_key)
