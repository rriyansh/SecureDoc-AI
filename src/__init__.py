"""SecureDoc AI v4 — Core foundation layer.

The ``core`` package provides dependency-free primitives that every other
module in the project builds upon:

- **Configuration** (:mod:`src.core.config`) — typed, validated settings
- **Context** (:mod:`src.core.context`) — request-scoped contextvars
- **Exceptions** (:mod:`src.core.exceptions`) — unified error hierarchy
- **Logging** (:mod:`src.core.logger`) — structured, redacted, correlated

Nothing in ``src.core`` may import from sibling packages (``src.db``,
``src.rag``, etc.). This keeps the dependency graph acyclic and makes the
entire project trivially testable.

Public API
----------
>>> from src.core import get_settings, get_logger, AppError
>>> settings = get_settings()
>>> log = get_logger("example")
>>> log.info(f"running in {settings.environment}")
"""

from __future__ import annotations

# --- Configuration ---
from src.core.config import Settings, get_settings

# --- Context ---
from src.core.context import (
    clear_request_context,
    current_path,
    current_principal,
    current_request_id,
    current_user_id,
    request_context,
    set_request_context,
)

# --- Exceptions ---
from src.core.exceptions import (
    AppError,
    AuthError,
    CircuitOpenError,
    ConflictError,
    DependencyError,
    ForbiddenError,
    NotFoundError,
    PipelineError,
    RateLimitError,
    SecurityViolation,
    ValidationError,
    error_to_dict,
)

# --- Logging ---
from src.core.logger import LogConfig, get_logger, setup_logger

__all__ = [
    # Config
    "Settings",
    "get_settings",
    # Context
    "set_request_context",
    "clear_request_context",
    "request_context",
    "current_request_id",
    "current_principal",
    "current_path",
    "current_user_id",
    # Exceptions
    "AppError",
    "AuthError",
    "ForbiddenError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ValidationError",
    "SecurityViolation",
    "PipelineError",
    "DependencyError",
    "CircuitOpenError",
    "error_to_dict",
    # Logging
    "get_logger",
    "setup_logger",
    "LogConfig",
]

__version__ = "4.0.0"
