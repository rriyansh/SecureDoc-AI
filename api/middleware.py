"""Middleware: request context, security headers, IP allowlist, signing."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config import get_settings
from src.context import set_request_context
from src.logger import get_logger
from src.request_signer import verify_signature

log = get_logger("api.middleware")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_context(rid)
        request.state.request_id = rid
        start = time.perf_counter()

        s = get_settings()
        # Body size guard
        max_bytes = s.api_max_request_size_mb * 1024 * 1024
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > max_bytes:
            return JSONResponse(
                status_code=413,
                content={"error": f"Payload too large (>{s.api_max_request_size_mb} MB)"},
            )

        # IP allowlist (optional)
        if s.ip_allowlist:
            client_ip = request.client.host if request.client else ""
            if client_ip not in s.ip_allowlist:
                return JSONResponse(status_code=403, content={"error": "IP not allowed"})

        # Request signing (optional)
        if s.request_signing_enabled and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            body = await request.body()
            try:
                verify_signature(
                    method=request.method,
                    path=request.url.path,
                    body=body,
                    timestamp=request.headers.get("X-Timestamp"),
                    signature=request.headers.get("X-Signature"),
                )
            except Exception as e:
                return JSONResponse(status_code=401, content={"error": str(e)})

        try:
            response = await call_next(request)
        except Exception:
            log.exception(f"Unhandled error: {request.url.path}")
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = rid
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
            f"({elapsed_ms:.1f} ms, rid={rid[:8]})"
        )
        return response
