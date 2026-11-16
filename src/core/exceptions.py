"""Application exception hierarchy.

Every error the application can raise derives from :class:`AppError`. This
gives us three guarantees:

1. **Stable wire format** — the API returns ``{error, code, request_id}``
   regardless of error type.
2. **Correct HTTP status** — each subclass carries its ``status_code``.
3. **Auditability** — the ``code`` field is stable for alerting/dashboards.

Never raise bare ``Exception`` or ``HTTPException`` from business logic; use
the appropriate subclass below.
"""

from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------- #
# Base                                                                         #
# --------------------------------------------------------------------------- #

class AppError(Exception):
    """Base class for all application errors.

    Attributes
    ----------
    code : str
        Stable machine-readable identifier (for alerts/dashboards).
    status_code : int
        HTTP status the API layer should return.
    details : dict[str, Any] | None
        Optional structured context (never contains secrets).
    """

    code: str = "internal_error"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": str(self),
            "code": self.code,
            **({"details": self.details} if self.details else {}),
        }

    def __repr__(self) -> str:
        return f"<{type(self).__name__} code={self.code!r} msg={str(self)!r}>"


# --------------------------------------------------------------------------- #
# 4xx client errors                                                            #
# --------------------------------------------------------------------------- #

class AuthError(AppError):
    """Authentication failed or missing."""

    code = "auth_error"
    status_code = 401


class ForbiddenError(AppError):
    """Authenticated but not allowed."""

    code = "forbidden"
    status_code = 403


class NotFoundError(AppError):
    """Resource does not exist."""

    code = "not_found"
    status_code = 404


class ConflictError(AppError):
    """Resource already exists (e.g. duplicate email)."""

    code = "conflict"
    status_code = 409


class ValidationError(AppError):
    """Input failed validation."""

    code = "validation_error"
    status_code = 422


class RateLimitError(AppError):
    """Rate limit exceeded."""

    code = "rate_limited"
    status_code = 429

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: int = 60,
    ) -> None:
        super().__init__(message, details={"retry_after": retry_after})
        self.retry_after = retry_after


class SecurityViolation(AppError):
    """Input triggered a security rule (injection, PII, encoded payload)."""

    code = "security_violation"
    status_code = 400


# --------------------------------------------------------------------------- #
# 5xx server errors                                                            #
# --------------------------------------------------------------------------- #

class InternalError(AppError):
    """Unexpected server-side error (never exposed to client)."""

    code = "internal_error"
    status_code = 500


class PipelineError(AppError):
    """RAG pipeline failure (LLM, retrieval, or guardrail)."""

    code = "pipeline_error"
    status_code = 500


class DependencyError(AppError):
    """A downstream dependency (DB, Redis, OpenAI) is unhealthy."""

    code = "dependency_unavailable"
    status_code = 503


class CircuitOpenError(AppError):
    """Circuit breaker is open — fast-fail to protect downstream."""

    code = "circuit_open"
    status_code = 503

    def __init__(self, message: str, *, retry_after: int = 30) -> None:
        super().__init__(message, details={"retry_after": retry_after})
        self.retry_after = retry_after


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def error_to_dict(exc: Exception) -> dict[str, Any]:
    """Convert any exception to the API wire format.

    Non-:class:`AppError` exceptions become opaque 500s — never leak internals.
    """
    if isinstance(exc, AppError):
        return exc.to_dict()
    return {"error": "Internal server error", "code": "internal_error"}


def is_client_error(exc: Exception) -> bool:
    """True if the error is a client fault (4xx)."""
    return isinstance(exc, AppError) and 400 <= exc.status_code < 500


def http_status_for(exc: Exception) -> int:
    """Map any exception to an HTTP status code."""
    if isinstance(exc, AppError):
        return exc.status_code
    return 500
