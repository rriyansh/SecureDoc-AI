"""Security middleware for input/output guardrails."""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from src.config import config
from src.logger import get_logger
from src.security import sanitize_input, detect_pii, redact_pii
from src.metrics import metrics
from src.audit import get_audit_logger, AuditEventType, AuditLevel

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to all requests."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware with input/output guardrails."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.input_rails_enabled = config.input_rails_enabled
        self.output_rails_enabled = config.output_rails_enabled

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = getattr(request.state, "request_id", None)

        # Sanitize query parameters
        if self.input_rails_enabled:
            sanitized_params = {}
            for key, value in request.query_params.items():
                sanitized_params[key] = sanitize_input(value)
            # Note: Can't modify request.query_params directly in Starlette
            # This would need a custom Request subclass

        # Process request body for POST/PUT
        if request.method in ("POST", "PUT", "PATCH") and self.input_rails_enabled:
            # This is a simplified version - in production you'd need to
            # properly handle body parsing and reconstruction
            pass

        try:
            response = await call_next(request)

            # Add security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Record metrics
            duration = time.time() - start_time
            metrics.record_http_request(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code,
                duration=duration,
            )

            return response

        except Exception as e:
            logger.error("Request failed: %s", e, exc_info=True)
            duration = time.time() - start_time
            metrics.record_http_request(
                method=request.method,
                endpoint=request.url.path,
                status=500,
                duration=duration,
            )
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        from src.rate_limiter import get_rate_limiter
        self.limiter = get_rate_limiter("api")

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and metrics
        if request.url.path in ("/health", "/ready", "/metrics", "/v1/health", "/v1/ready", "/v1/metrics"):
            return await call_next(request)

        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        user_id = getattr(request.state, "user_id", None)
        key = user_id or client_ip

        # Check rate limit
        allowed, info = self.limiter.check_limit(key)
        if not allowed:
            from src.metrics import metrics
            metrics.record_rate_limit_exceeded("api", key)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "X-RateLimit-Limit": str(int(info["limit"])),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(info.get("reset_at", 0))),
                    "Retry-After": str(int(info.get("retry_after", 1))),
                },
            )

        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(int(info["limit"]))
        response.headers["X-RateLimit-Remaining"] = str(int(info["remaining"]))
        if info.get("reset_at"):
            response.headers["X-RateLimit-Reset"] = str(int(info["reset_at"]))
        return response


class GuardrailsMiddleware(BaseHTTPMiddleware):
    """NeMo Guardrails integration middleware (placeholder)."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.enabled = config.input_rails_enabled or config.output_rails_enabled

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        # In production, integrate with NeMo Guardrails here
        # For now, just pass through
        return await call_next(request)