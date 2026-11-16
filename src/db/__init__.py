"""SecureDoc AI v4 — Database layer.

SQLAlchemy 2.0 async ORM. This package owns:

- **Base** — declarative base class with reusable mixins
- **Session** — async engine, session factory, FastAPI dependency
- **Models** — ``User``, ``ApiKey``, ``AuditLog``
- **Repositories** — query logic for entities that need it

Dependency direction
--------------------
- ``src.db`` may import from ``src.core`` (config, logging, exceptions).
- ``src.db`` MUST NOT import from ``src.security``, ``src.rag``, ``src.cache``,
  ``src.resilience``, or ``api/``. Repositories are pure data access.

Public API
----------
>>> from src.db import Base, get_db, User, ApiKeyRepository
"""

from __future__ import annotations

# --- Base & session ---
from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from src.db.session import (
    SessionFactory,
    dispose_engine,
    engine,
    get_db,
    healthcheck,
    session_scope,
)

# --- Models ---
from src.db.models import ApiKey, AuditLog, User

# --- Repositories ---
from src.db.repositories.api_key import ApiKeyRepository
from src.db.repositories.audit import AuditRepository
from src.db.repositories.user import UserRepository

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    # Session
    "engine",
    "SessionFactory",
    "get_db",
    "session_scope",
    "healthcheck",
    "dispose_engine",
    # Models
    "User",
    "ApiKey",
    "AuditLog",
    # Repositories
    "UserRepository",
    "ApiKeyRepository",
    "AuditRepository",
]
