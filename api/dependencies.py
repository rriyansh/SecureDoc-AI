"""API dependencies for authentication, rate limiting, and common parameters."""

from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, Header, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config import config
from src.auth import verify_api_key, verify_jwt_token, require_scopes, APIKey, TokenPayload
from src.rate_limiter import get_rate_limiter
from src.logger import get_logger

logger = get_logger(__name__)

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Extract and validate user from API key or JWT token."""
    user_info = {
        "user_id": "anonymous",
        "scopes": [],
        "auth_method": "none",
        "api_key": None,
        "token_payload": None,
    }

    # Try API key first (from header)
    if x_api_key:
        api_key_obj = verify_api_key(x_api_key)
        if api_key_obj:
            user_info["user_id"] = api_key_obj.key_id
            user_info["scopes"] = api_key_obj.scopes
            user_info["auth_method"] = "api_key"
            user_info["api_key"] = api_key_obj
            return user_info

    # Try Bearer token (JWT)
    if credentials and credentials.credentials:
        token_payload = verify_jwt_token(credentials.credentials)
        if token_payload:
            user_info["user_id"] = token_payload.sub
            user_info["scopes"] = token_payload.scopes
            user_info["auth_method"] = "jwt"
            user_info["token_payload"] = token_payload
            return user_info

    return user_info


async def require_auth(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Require authenticated user."""
    if user["auth_method"] == "none":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_scopes_dependency(
    required_scopes: list,
    user: Dict[str, Any] = Depends(require_auth),
) -> Dict[str, Any]:
    """Require specific scopes."""
    if not require_scopes(user.get("token_payload") or user.get("api_key"), required_scopes):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required scopes: {required_scopes}",
        )
    return user


def require_admin(user: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
    """Require admin scope."""
    if "admin" not in user["scopes"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def check_rate_limit(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
    scope: str = "api",
) -> Dict[str, Any]:
    """Check rate limit for request."""
    limiter = get_rate_limiter(scope)
    key = user["user_id"] if user["auth_method"] != "none" else request.client.host

    allowed, info = limiter.check_limit(key)
    if not allowed:
        from src.metrics import metrics
        metrics.record_rate_limit_exceeded(scope, key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(int(info["limit"])),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(info.get("reset_at", 0))),
                "Retry-After": str(int(info.get("retry_after", 1))),
            },
        )

    # Add rate limit headers to response
    request.state.rate_limit_info = info
    return user


async def get_pipeline():
    """Get RAG pipeline instance."""
    from src.rag_pipeline import SecureRAGPipeline
    return SecureRAGPipeline()


class CommonParams:
    """Common query parameters."""

    def __init__(
        self,
        use_cache: bool = True,
        use_rewrite: bool = True,
        top_k: Optional[int] = None,
    ):
        self.use_cache = use_cache
        self.use_rewrite = use_rewrite
        self.top_k = top_k or config.top_k