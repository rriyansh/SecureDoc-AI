"""Custom exception hierarchy with error codes."""

from __future__ import annotations


class SecureDocError(Exception):
    """Base exception with error code and HTTP status hint."""

    code: str = "internal_error"
    status_code: int = 500

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class AuthenticationError(SecureDocError):
    code = "auth_error"
    status_code = 401


class AuthorizationError(SecureDocError):
    code = "forbidden"
    status_code = 403


class RateLimitError(SecureDocError):
    code = "rate_limited"
    status_code = 429


class ValidationError(SecureDocError):
    code = "validation_error"
    status_code = 422


class SecurityViolation(SecureDocError):
    code = "security_violation"
    status_code = 400


class PipelineError(SecureDocError):
    code = "pipeline_error"
    status_code = 500


class DependencyError(SecureDocError):
    code = "dependency_unavailable"
    status_code = 503


class CircuitOpenError(SecureDocError):
    code = "circuit_open"
    status_code = 503
