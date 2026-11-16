"""Repositories — data access layer for entities with real query needs.

Only three entities warrant repositories:

* **UserRepository** — login, pagination, admin listing
* **ApiKeyRepository** — issue/redeem/revoke with hashing
* **AuditRepository** — hash-chained writes, retention, verification

Repositories receive an :class:`AsyncSession` in ``__init__`` and never open
their own sessions — the caller (route or ``session_scope()``) owns the
transaction boundary.
"""

from __future__ import annotations

from src.db.repositories.api_key import ApiKeyRepository
from src.db.repositories.audit import AuditRepository
from src.db.repositories.user import UserRepository

__all__ = ["UserRepository", "ApiKeyRepository", "AuditRepository"]
