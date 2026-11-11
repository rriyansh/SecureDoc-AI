"""Unified error responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.context import current_request_id
from src.exceptions import SecureDocError
from src.logger import get_logger

log = get_logger("api.errors")


def register(app: FastAPI) -> None:
    @app.exception_handler(SecureDocError)
    async def _secure_error(request: Request, exc: SecureDocError) -> JSONResponse:
        log.warning(f"{exc.code}: {exc}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": str(exc),
                "code": exc.code,
                "request_id": current_request_id(),
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception(f"Unhandled: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "code": "internal_error",
                "request_id": current_request_id(),
            },
        )
