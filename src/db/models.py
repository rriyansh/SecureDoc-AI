"""ORM models: User, ApiKey, AuditLog.

Schema parity
-------------
Every column here is present in ``alembic/versions/001_initial.py``. If you
change a column, change **both** files, and generate a new migration — never
edit the initial migration in place (that breaks already-migrated databases).

Indexes
-------
* ``users.email`` — unique (login lookup)
* ``api_keys.prefix`` — unique (key lookup — first 12 chars)
* ``api_keys.user_id`` — plain (list keys per user)
* ``audit_logs.ts``, ``audit_logs.event``, ``audit_logs.principal``,
  ``audit_logs.request_id``, ``audit_logs.chain_hash`` — all plain
  (dashboard queries, chain verification, retention scans)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


# --------------------------------------------------------------------------- #
# User                                                                         #
# --------------------------------------------------------------------------- #

class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An authenticated application user.

    Attributes
    ----------
    email : str
        Unique, lowercased. Used as the login identifier.
    password_hash : str
        bcrypt hash — never the plaintext (see ``src.security.auth``).
    is_active : bool
        Soft-delete flag. Inactive users cannot log in.
    is_admin : bool
        Grants access to ``/api/v1/admin/*`` endpoints and the admin UI.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Relationships
    # ``lazy="selectin"`` eagerly loads API keys with the user in one extra
    # query — avoids N+1 when iterating users and their keys. ``cascade="all,
    # delete-orphan"`` means deleting a user deletes their keys (there's also
    # ON DELETE CASCADE at the DB level — belt and suspenders).
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id[:8]} email={self.email!r}>"


# --------------------------------------------------------------------------- #
# ApiKey                                                                       #
# --------------------------------------------------------------------------- #

class ApiKey(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A long-lived API credential for programmatic access.

    Security model
    --------------
    * **Plaintext is shown to the user exactly once** (at creation).
    * We store only ``key_hash = SHA-256(raw_key)`` — not bcrypt, because
      lookup-by-prefix + bcrypt-verify per candidate is O(active_keys) slow.
      SHA-256 + constant-time compare is correct here because keys are
      64-char random hex (256 bits entropy) — pre-image attack is infeasible.
    * ``prefix`` is the first 12 chars, used as an index for O(1) lookup.

    Attributes
    ----------
    user_id : str
        Owner. Cascades on user delete.
    name : str
        User-facing label ("CI pipeline", "Mobile app").
    prefix : str
        First 12 chars — unique, indexed. Not secret on its own (48 bits).
    key_hash : str
        SHA-256 hex digest of the full raw key.
    is_active : bool
        False after revocation. Revoked keys fail auth immediately.
    expires_at : datetime | None
        Optional hard expiry. ``None`` = no expiry.
    last_used_at : datetime | None
        Updated on every successful auth — audit + stale-key cleanup.
    """

    __tablename__ = "api_keys"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    prefix: Mapped[str] = mapped_column(
        String(16),
        unique=True,
        nullable=False,
        index=True,
    )
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="api_keys", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ApiKey id={self.id[:8]} prefix={self.prefix} name={self.name!r}>"


# --------------------------------------------------------------------------- #
# AuditLog                                                                     #
# --------------------------------------------------------------------------- #

class AuditLog(Base):
    """Tamper-evident audit entry with hash chaining.

    The ``chain_hash`` of each row is::

        SHA256(prev_chain_hash || serialized_payload)

    where ``prev_chain_hash`` is the ``chain_hash`` of the previous row (or
    64 zeros for the very first row). Modifying any row invalidates every
    subsequent ``chain_hash`` — verified by
    :meth:`AuditRepository.verify_chain`.

    Attributes
    ----------
    ts : datetime
        Server-set timestamp (not app clock — see TimestampMixin rationale).
    event : str
        Stable short identifier (``"query"``, ``"query_blocked"``, ...).
    principal : str | None
        Opaque identifier of the caller ("key:abc123:def456", "jwt:user-id").
    request_id : str | None
        Correlates with the request-scoped context / log lines.
    action : str | None
        Semantic action within a request (``"query"``, ``"login"``).
    ip : str | None
        Caller IP if available.
    meta : dict | None
        Structured free-form data (latency, reason, error). Never contains
        secrets — the AuditRepository filters before insert.
    prev_hash : str | None
        ``chain_hash`` of the previous row (``None`` for the first row).
    chain_hash : str | None
        This row's hash. Indexed for verification scans.
    """

    __tablename__ = "audit_logs"

    # BigInteger auto-increment — natural ordering, cheap pagination
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    principal: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    request_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    action: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chain_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} event={self.event!r} principal={self.principal!r}>"
