"""Admin API routes."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.dependencies import get_current_user, require_admin, require_scopes_dependency
from src.auth import api_key_manager, APIKey
from src.cache import query_cache
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = Field(default_factory=list)
    expires_days: Optional[int] = Field(None, ge=1, le=365)


class APIKeyCreateResponse(BaseModel):
    key_id: str
    name: str
    scopes: List[str]
    plaintext_key: str
    created_at: str
    expires_at: Optional[str] = None


class APIKeyListResponse(BaseModel):
    keys: List[dict]


class CacheStatsResponse(BaseModel):
    exact: dict
    semantic: dict


class RateLimitStatusResponse(BaseModel):
    scope: str
    limit: int
    remaining: float
    reset_at: float


@router.post(
    "/api-keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Create a new API key with specified scopes.",
)
async def create_api_key(
    request: APIKeyCreateRequest,
    user: dict = Depends(require_admin),
) -> APIKeyCreateResponse:
    """Create a new API key."""
    plaintext_key = api_key_manager.create_key(
        name=request.name,
        scopes=request.scopes,
        expires_days=request.expires_days,
    )

    # Get the created key to return details
    created_key = None
    for key in api_key_manager.list_keys():
        if key.name == request.name and key.key_id not in [k.key_id for k in api_key_manager.list_keys()[:-1]]:
            created_key = key
            break

    if not created_key:
        # Fallback - get the most recent
        keys = api_key_manager.list_keys()
        created_key = keys[-1] if keys else None

    if not created_key:
        raise HTTPException(status_code=500, detail="Failed to retrieve created key")

    return APIKeyCreateResponse(
        key_id=created_key.key_id,
        name=created_key.name,
        scopes=created_key.scopes,
        plaintext_key=plaintext_key,
        created_at=created_key.created_at.isoformat(),
        expires_at=created_key.expires_at.isoformat() if created_key.expires_at else None,
    )


@router.get(
    "/api-keys",
    response_model=APIKeyListResponse,
    summary="List API keys",
    description="List all API keys (without secrets).",
)
async def list_api_keys(user: dict = Depends(require_admin)) -> APIKeyListResponse:
    """List all API keys."""
    keys = api_key_manager.list_keys()
    return APIKeyListResponse(
        keys=[
            {
                "key_id": k.key_id,
                "name": k.name,
                "scopes": k.scopes,
                "created_at": k.created_at.isoformat(),
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "last_used": k.last_used.isoformat() if k.last_used else None,
                "is_active": k.is_active,
            }
            for k in keys
        ]
    )


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API key",
    description="Revoke an API key by ID.",
)
async def revoke_api_key(key_id: str, user: dict = Depends(require_admin)):
    """Revoke an API key."""
    success = api_key_manager.revoke_key(key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")


@router.get(
    "/cache/stats",
    response_model=CacheStatsResponse,
    summary="Cache statistics",
    description="Get cache statistics for monitoring.",
)
async def cache_stats(user: dict = Depends(require_admin)) -> CacheStatsResponse:
    """Get cache statistics."""
    stats = query_cache.stats()
    return CacheStatsResponse(
        exact=stats["exact"],
        semantic=stats["semantic"],
    )


@router.post(
    "/cache/clear",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear cache",
    description="Clear all caches.",
)
async def clear_cache(user: dict = Depends(require_admin)):
    """Clear all caches."""
    query_cache.clear()


@router.get(
    "/rate-limit/status",
    response_model=RateLimitStatusResponse,
    summary="Rate limit status",
    description="Get current rate limit status for the requesting user.",
)
async def rate_limit_status(
    user: dict = Depends(get_current_user),
) -> RateLimitStatusResponse:
    """Get rate limit status for current user."""
    from src.rate_limiter import get_rate_limiter

    limiter = get_rate_limiter("api")
    key = user["user_id"] if user["auth_method"] != "none" else "anonymous"
    status_info = limiter.get_status(key)

    return RateLimitStatusResponse(
        scope="api",
        limit=int(status_info["limit"]),
        remaining=status_info["remaining"],
        reset_at=status_info["reset_at"],
    )


class ConfigResponse(BaseModel):
    config: dict


@router.get(
    "/config",
    response_model=ConfigResponse,
    summary="Get configuration",
    description="Get non-sensitive configuration (requires admin).",
)
async def get_config(user: dict = Depends(require_admin)) -> ConfigResponse:
    """Get configuration (sanitized)."""
    from src.config import config as config_obj
    from src.security import sanitize_dict

    # Get config as dict and sanitize
    config_dict = config_obj._data
    sanitized = sanitize_dict(config_dict)

    return ConfigResponse(config=sanitized)


class AuditLogQuery(BaseModel):
    limit: int = Field(100, ge=1, le=1000)
    event_type: Optional[str] = None
    level: Optional[str] = None
    user_id: Optional[str] = None


@router.post(
    "/audit/query",
    summary="Query audit logs",
    description="Query audit logs with filters (requires admin).",
)
async def query_audit_logs(
    query: AuditLogQuery,
    user: dict = Depends(require_admin),
) -> dict:
    """Query audit logs (placeholder)."""
    return {
        "detail": "Audit log querying not yet implemented",
        "query": query.dict(),
    }