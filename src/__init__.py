"""SecureDoc AI v4 — Production-grade Retrieval-Augmented Generation platform.

Top-level package. Importing ``src`` should be cheap and side-effect-free —
this module does **not** open DB connections, load models, or touch the
filesystem. All lazily-initialized singletons live in their respective
subpackages and only fire on first use.

Package layout
--------------
::

    src/
    ├── core/          config, logging, exceptions, context
    ├── db/            SQLAlchemy models, session, repositories
    ├── security/      auth, crypto, pii, sanitize, request signing
    ├── cache/         memory + redis backends, factory
    ├── resilience/    circuit breaker, rate limiter, dedup, anomaly
    ├── observability/ Prometheus metrics, health probes
    └── rag/           ingest, retriever, reranker, pipeline, evaluate

Dependency direction (enforced by convention, not tooling)
----------------------------------------------------------
::

    core         ← no internal dependencies
    db           ← core
    security     ← core, db (lazy)
    cache        ← core, security, observability
    resilience   ← core, observability
    observability ← core, db (lazy), cache (lazy)
    rag          ← core, security, resilience, observability

No package may import from ``api/`` — the API is a downstream consumer.
No package may import upward (e.g. ``core`` must not import ``db``).

Usage
-----
Prefer top-level imports for the most common symbols::

    >>> from src import get_settings, get_logger, scan, safe_query
    >>> settings = get_settings()
    >>> log = get_logger("example")

Or import from the specific subpackage when you need something less common::

    >>> from src.db.repositories.api_key import ApiKeyRepository
    >>> from src.rag.retriever import build_hybrid_retriever
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Version                                                                      #
# --------------------------------------------------------------------------- #

# Semantic version. Keep in sync with ``pyproject.toml`` and
# ``APP_VERSION`` default in ``src.core.config.Settings``.
__version__ = "4.0.0"

# Public API for tools that introspect the package.
__author__ = "SecureDoc AI Team"
__license__ = "MIT"


# --------------------------------------------------------------------------- #
# Curated re-exports                                                           #
# --------------------------------------------------------------------------- #
#
# These are the symbols used in **every** module and script. Importing them
# here saves a lot of ``from src.core.config import get_settings`` noise in
# short modules and tests. Everything else should be imported from its
# specific subpackage — this list is intentionally small.

# --- Config (used everywhere) ---
from src.core.config import Settings, get_settings

# --- Logging (used everywhere) ---
from src.core.logger import get_logger

# --- Context (used in middleware and pipelines) ---
from src.core.context import (
    current_principal,
    current_request_id,
    current_user_id,
    request_context,
    set_request_context,
)

# --- Exceptions (used by every layer's error handling) ---
from src.core.exceptions import (
    AppError,
    AuthError,
    CircuitOpenError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    SecurityViolation,
    ValidationError,
)

# --- Security: the two most-used entry points ---
from src.security.pii import detect_pii, redact_pii
from src.security.sanitize import ScanResult, scan

# --- RAG: the two functions every caller needs ---
from src.rag.pipeline import build_rag_chain, safe_query

# --- Health (used by scripts and probes) ---
from src.observability.health import aggregate as health_aggregate


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

__all__ = [
    # Version
    "__version__",
    "__author__",
    "__license__",
    # Config
    "Settings",
    "get_settings",
    # Logging
    "get_logger",
    # Context
    "set_request_context",
    "request_context",
    "current_request_id",
    "current_principal",
    "current_user_id",
    # Exceptions
    "AppError",
    "AuthError",
    "ForbiddenError",
    "NotFoundError",
    "RateLimitError",
    "ValidationError",
    "SecurityViolation",
    "CircuitOpenError",
    # Security
    "scan",
    "ScanResult",
    "detect_pii",
    "redact_pii",
    # RAG
    "build_rag_chain",
    "safe_query",
    # Health
    "health_aggregate",
]
