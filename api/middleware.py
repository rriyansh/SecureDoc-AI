"""Security headers + request context middleware."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config import get_settings
from src.logger import get_logger

log = get_logger("api.middleware")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start = time.perf_counter()

        s = get_settings()
        max_bytes = s.api_max_request_size_mb * 1024 * 1024
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Payload too large (>{s.api_max_request_size_mb} MB)"},
            )

        try:
            response = await call_next(request)
        except Exception:
            log.exception(f"Unhandled error: {request.url.path}")
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"

        if s.security_headers_enabled:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
            if s.environment == "production":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        log.info(
            f"{request.method} {request.url.path} → {response.status_code} "
            f"({elapsed_ms:.1f} ms, rid={request_id[:8]})"
        )
        return response
