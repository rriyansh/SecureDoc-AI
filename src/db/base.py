"""Declarative base and reusable column mixins.

Why mixins: the ``User`` and ``ApiKey`` tables both need ``id`` (UUID) and
timestamps. Duplicating those column definitions would drift over time. One
mixin per concept keeps them in sync and self-documenting.

Why not inheritance hierarchies: SQLAlchemy's single-table or joined-table
inheritance is powerful but adds query complexity. Our tables share **columns**,
not **behavior**, so plain mixins are the right tool (KISS).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Common declarative base for every ORM model.

    Every table inherits from this so ``Base.metadata`` sees all tables —
    which is required for Alembic autogenerate and ``metadata.create_all()``.
    """

    def to_dict(self) -> dict:
        """Shallow serialisation — useful for tests and audit meta."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


def _uuid_str() -> str:
    """Generate a UUID4 string. Matches the ``String(36)`` columns."""
    return str(uuid.uuid4())


class UUIDPrimaryKeyMixin:
    """Adds a UUID string primary key named ``id``.

    String UUIDs (not native UUID type) are used because:

    * The same schema runs on SQLite in tests (SQLite has no UUID type).
    * The values are URL-safe and JSON-serialisable.
    * Indexes on ``String(36)`` are fast enough at our scale.
    """

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
        index=False,
    )


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns with server defaults.

    Server-side defaults (``func.now()``) are used so the DB clock — not the
    app clock — determines the value. This prevents clock-skew between app
    replicas from producing inconsistent timestamps.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
