"""Request logging and timing middleware."""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.logger import get_logger

log = get_logger("api.middleware")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request ID and log timing for every request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover - safety net
            log.exception(f"Unhandled error on {request.url.path}: {exc}")
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
        log.info(
            f"{request.method} {request.url.path} -> {response.status_code} "
            f"({elapsed_ms:.1f} ms, rid={request_id[:8]})"
        )
        return response
