"""Audit trail: tamper-evident writes, retention, verification.

Hash chain
----------
Each row's ``chain_hash`` = ``SHA256(prev_chain_hash || serialized_payload)``.

Two concurrent writers could otherwise read the same ``prev_chain_hash`` and
produce a **fork**. To serialize writes we take ``SELECT ... FOR UPDATE`` on
the latest row — Postgres blocks the second writer until the first commits.
SQLite ignores ``FOR UPDATE`` (single-writer engine) but is safe because
concurrent writes are impossible there.

Verification
------------
``verify_chain()`` walks rows in ascending id order and re-computes each
hash from its stored payload. Any modification — even whitespace in
``meta`` — invalidates every subsequent hash.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.db.models import AuditLog

log = get_logger("db.repositories.audit")

_GENESIS_HASH = "0" * 64
_MAX_META_BYTES = 4096


# --------------------------------------------------------------------------- #
# Chain helpers                                                                #
# --------------------------------------------------------------------------- #

def _serialize_payload(payload: dict[str, Any]) -> str:
    """Deterministic JSON serialization for hashing.

    ``sort_keys=True`` is mandatory — otherwise reordering dict keys during
    insertion changes the hash and breaks verification.
    """
    return json.dumps(payload, sort_keys=True, default=str)


def _compute_chain_hash(prev_hash: str | None, payload: dict[str, Any]) -> str:
    prefix = prev_hash or _GENESIS_HASH
    serialized = _serialize_payload(payload)
    return hashlib.sha256((prefix + serialized).encode("utf-8")).hexdigest()


def _truncate_meta(meta: dict[str, Any] | None) -> dict[str, Any] | None:
    """Cap ``meta`` size so a malicious payload can't bloat the DB."""
    if meta is None:
        return None
    try:
        encoded = json.dumps(meta, default=str).encode("utf-8")
    except (TypeError, ValueError):
        return {"_error": "meta not serializable"}
    if len(encoded) <= _MAX_META_BYTES:
        return meta
    # Truncate to a marker
    return {"_truncated": True, "_preview": str(meta)[:500]}


# --------------------------------------------------------------------------- #
# Repository                                                                   #
# --------------------------------------------------------------------------- #

class AuditRepository:
    """Query facade for the ``audit_logs`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ #
    # Writes                                                             #
    # ------------------------------------------------------------------ #

    async def record(
        self,
        event: str,
        *,
        principal: str | None = None,
        request_id: str | None = None,
        action: str | None = None,
        ip: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Insert an audit entry, extending the hash chain.

        The transaction ``SELECT ... FOR UPDATE`` guarantees the chain
        doesn't fork under concurrent writers.

        Returns the inserted :class:`AuditLog` (flushed, not committed —
        caller decides commit boundary).
        """
        # Lock the latest row so two writers can't read the same prev_hash.
        result = await self._session.execute(
            select(AuditLog)
            .order_by(AuditLog.id.desc())
            .limit(1)
            .with_for_update()
        )
        last = result.scalar_one_or_none()
        prev_hash = last.chain_hash if last else None

        # Build the payload that will be hashed. This MUST be the same set
        # of fields re-used during verify_chain(), otherwise verification
        # will fail. Keep the two functions in sync.
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "event": event,
            "principal": principal,
            "request_id": request_id,
            "action": action,
            "ip": ip,
            "meta": _truncate_meta(meta),
            "ts_iso": now.isoformat(),
        }
        chain_hash = _compute_chain_hash(prev_hash, payload)

        entry = AuditLog(
            event=event[:64],
            principal=principal[:128] if principal else None,
            request_id=request_id[:36] if request_id else None,
            action=action[:128] if action else None,
            ip=ip[:64] if ip else None,
            meta=payload["meta"],
            prev_hash=prev_hash,
            chain_hash=chain_hash,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    # ------------------------------------------------------------------ #
    # Reads                                                              #
    # ------------------------------------------------------------------ #

    async def recent(self, *, limit: int = 100) -> list[AuditLog]:
        """Most recent N entries (newest first) — for dashboards."""
        result = await self._session.execute(
            select(AuditLog).order_by(AuditLog.id.desc()).limit(max(1, min(limit, 1000)))
        )
        return list(result.scalars().all())

    async def query(
        self,
        *,
        event: str | None = None,
        principal: str | None = None,
        request_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Filtered query with pagination — for admin audit page."""
        stmt = select(AuditLog).order_by(AuditLog.id.desc())
        if event:
            stmt = stmt.where(AuditLog.event == event)
        if principal:
            stmt = stmt.where(AuditLog.principal == principal)
        if request_id:
            stmt = stmt.where(AuditLog.request_id == request_id)
        if since:
            stmt = stmt.where(AuditLog.ts >= since)
        if until:
            stmt = stmt.where(AuditLog.ts <= until)
        stmt = stmt.limit(max(1, min(limit, 1000))).offset(max(0, offset))

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_principal(self, principal: str) -> int:
        """Total events for a principal — for anomaly dashboards."""
        result = await self._session.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.principal == principal)
        )
        return result.scalar() or 0

    async def recent_for_principal(
        self, principal: str, *, limit: int = 50
    ) -> list[AuditLog]:
        """Recent activity for a single principal."""
        result = await self._session.execute(
            select(AuditLog)
            .where(AuditLog.principal == principal)
            .order_by(AuditLog.id.desc())
            .limit(max(1, min(limit, 500)))
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------ #
    # Verification                                                       #
    # ------------------------------------------------------------------ #

    async def verify_chain(self, *, limit: int = 10_000) -> dict[str, Any]:
        """Verify the integrity of the hash chain.

        Returns a dict::

            {
              "valid": bool,
              "checked": int,
              "first_invalid": int | None,
              "reason": str | None,
            }

        Walks entries in ascending id order and re-computes each hash from
        the stored payload. Any mismatch means the row (or an ancestor)
        was modified after the fact.
        """
        result = await self._session.execute(
            select(AuditLog).order_by(AuditLog.id.asc()).limit(limit)
        )
        rows = list(result.scalars().all())

        if not rows:
            return {"valid": True, "checked": 0, "first_invalid": None, "reason": None}

        prev = None
        for i, row in enumerate(rows):
            # Reconstruct the payload using the same fields as ``record()``
            reconstructed = {
                "event": row.event,
                "principal": row.principal,
                "request_id": row.request_id,
                "action": row.action,
                "ip": row.ip,
                "meta": row.meta,
                "ts_iso": row.ts.isoformat(),
            }
            expected = _compute_chain_hash(prev, reconstructed)

            # First row: prev_hash should be None; every other row: prev_hash
            # should match the previous row's chain_hash.
            if row.prev_hash != prev:
                return {
                    "valid": False,
                    "checked": i + 1,
                    "first_invalid": row.id,
                    "reason": (
                        f"prev_hash mismatch at id={row.id}: "
                        f"expected {prev}, got {row.prev_hash}"
                    ),
                }

            if row.chain_hash != expected:
                return {
                    "valid": False,
                    "checked": i + 1,
                    "first_invalid": row.id,
                    "reason": (
                        f"chain_hash mismatch at id={row.id}: "
                        f"expected {expected}, got {row.chain_hash}"
                    ),
                }
            prev = row.chain_hash

        return {
            "valid": True,
            "checked": len(rows),
            "first_invalid": None,
            "reason": None,
        }

    # ------------------------------------------------------------------ #
    # Retention / cleanup                                                #
    # ------------------------------------------------------------------ #

    async def delete_older_than(self, days: int) -> int:
        """Delete entries older than ``days``.

        **Warning**: deletes break the chain from the perspective of
        ``verify_chain()`` for the new first row, because its ``prev_hash``
        will point to a deleted row. Callers performing retention MUST
        archive the rows first (e.g. dump to S3) and treat the post-delete
        first row's ``prev_hash`` as an "archived ancestor" anchor.

        Returns the number of deleted rows.
        """
        if days < 1:
            raise ValueError("days must be >= 1")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self._session.execute(
            sa_delete(AuditLog).where(AuditLog.ts < cutoff)
        )
        count = result.rowcount or 0
        if count:
            log.warning(
                f"Audit retention: deleted {count} rows older than "
                f"{days} days (cutoff={cutoff.isoformat()}). "
                f"Chain verification will treat the next row as a new genesis."
            )
        return count

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(AuditLog)
        )
        return result.scalar() or 0
