"""API key lifecycle: issue, verify, revoke, cleanup.

Security model
--------------
* **Hashing**: SHA-256 — not bcrypt. Rationale: we look up by 12-char prefix
  then compare the full hash. bcrypt would make every failed attempt cost
  ~100ms; SHA-256 + constant-time compare is correct because the raw key is
  64 hex chars = 256 bits entropy (pre-image infeasible).
* **Plaintext**: returned exactly once from ``create()``. Never stored.
* **Revocation**: sets ``is_active=False`` — immediate effect, no cache.
* **Expiry**: checked on every ``lookup_by_raw_key`` call.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.db.models import ApiKey

log = get_logger("db.repositories.api_key")

# Length of the indexed prefix (12 hex chars = 48 bits, ~281 trillion values)
PREFIX_LEN = 12

# Raw key length: 32 bytes → 64 hex chars → 256 bits entropy
RAW_KEY_BYTES = 32


# --------------------------------------------------------------------------- #
# Hashing helpers                                                              #
# --------------------------------------------------------------------------- #

def hash_api_key(raw: str) -> str:
    """SHA-256 hex digest of the raw key.

    This is what we store. Deterministic so ``lookup_by_raw_key`` can
    re-hash the candidate and compare.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_raw_key() -> str:
    """Return a new 64-char hex raw API key (256 bits of entropy)."""
    return secrets.token_hex(RAW_KEY_BYTES)


# --------------------------------------------------------------------------- #
# Repository                                                                   #
# --------------------------------------------------------------------------- #

class ApiKeyRepository:
    """Query facade for the ``api_keys`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ #
    # Create                                                             #
    # ------------------------------------------------------------------ #

    async def create(
        self,
        user_id: str,
        name: str,
        *,
        expires_at: datetime | None = None,
        max_retries: int = 3,
    ) -> tuple[ApiKey, str]:
        """Issue a new API key.

        Returns
        -------
        tuple[ApiKey, str]
            ``(record, raw_key)``. The raw key is shown **exactly once** —
            the caller MUST surface it to the user immediately and never
            persist it. The record contains only ``key_hash``.

        Raises
        ------
        RuntimeError
            If prefix collision persists after ``max_retries`` attempts
            (probability ~0; would indicate a broken RNG).
        """
        name = name.strip()[:100] or "api-key"

        for attempt in range(1, max_retries + 1):
            raw = generate_raw_key()
            prefix = raw[:PREFIX_LEN]

            record = ApiKey(
                user_id=user_id,
                name=name,
                prefix=prefix,
                key_hash=hash_api_key(raw),
                expires_at=expires_at,
            )
            self._session.add(record)
            try:
                await self._session.flush()
                await self._session.refresh(record)
                log.info(
                    f"API key issued: id={record.id[:8]} "
                    f"user={user_id[:8]} name={name!r} "
                    f"(attempt {attempt})"
                )
                return record, raw
            except IntegrityError:
                # Prefix collision — extremely unlikely, but retry cleanly.
                await self._session.rollback()
                log.warning(
                    f"API key prefix collision on attempt {attempt} "
                    f"(prefix={prefix}) — retrying"
                )

        raise RuntimeError(
            f"Failed to generate unique API key after {max_retries} attempts"
        )

    # ------------------------------------------------------------------ #
    # Lookup / verification                                              #
    # ------------------------------------------------------------------ #

    async def lookup_by_raw_key(self, raw: str) -> ApiKey | None:
        """Find an active, non-expired key matching ``raw``.

        Returns ``None`` on any of: unknown prefix, hash mismatch, revoked,
        expired. Caller treats all four as "unauthorized" — the distinction
        is only useful for logging, which this method handles.

        **Constant-time compare** prevents timing-based enumeration.
        """
        if not raw or len(raw) < PREFIX_LEN:
            return None

        prefix = raw[:PREFIX_LEN]
        result = await self._session.execute(
            select(ApiKey).where(ApiKey.prefix == prefix)
        )
        record = result.scalar_one_or_none()
        if record is None:
            log.debug(f"API key prefix not found: {prefix}")
            return None

        if not record.is_active:
            log.debug(f"API key revoked: id={record.id[:8]}")
            return None

        if not secrets.compare_digest(record.key_hash, hash_api_key(raw)):
            log.warning(f"API key hash mismatch for prefix {prefix}")
            return None

        if record.expires_at is not None and record.expires_at < datetime.now(timezone.utc):
            log.debug(f"API key expired: id={record.id[:8]}")
            return None

        return record

    async def get_by_id(self, key_id: str) -> ApiKey | None:
        return await self._session.get(ApiKey, key_id)

    # ------------------------------------------------------------------ #
    # Usage tracking                                                     #
    # ------------------------------------------------------------------ #

    async def touch_last_used(self, key_id: str) -> None:
        """Update ``last_used_at`` — called on successful auth."""
        await self._session.execute(
            update(ApiKey)
            .where(ApiKey.id == key_id)
            .values(last_used_at=datetime.now(timezone.utc))
        )

    # ------------------------------------------------------------------ #
    # Listing                                                            #
    # ------------------------------------------------------------------ #

    async def list_for_user(self, user_id: str) -> list[ApiKey]:
        """All keys owned by a user, newest first."""
        result = await self._session.execute(
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_active_for_user(self, user_id: str) -> int:
        """Active key count — useful for rate limiting key issuance."""
        result = await self._session.execute(
            select(func.count())
            .select_from(ApiKey)
            .where(ApiKey.user_id == user_id, ApiKey.is_active.is_(True))
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------ #
    # Revocation                                                         #
    # ------------------------------------------------------------------ #

    async def revoke(self, key_id: str) -> bool:
        """Deactivate a key. Returns True if it existed and was active."""
        record = await self.get_by_id(key_id)
        if record is None:
            return False
        if not record.is_active:
            return False
        record.is_active = False
        await self._session.flush()
        log.info(f"API key revoked: id={key_id[:8]}")
        return True

    async def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke every active key for a user (e.g. on password compromise)."""
        result = await self._session.execute(
            update(ApiKey)
            .where(ApiKey.user_id == user_id, ApiKey.is_active.is_(True))
            .values(is_active=False)
        )
        count = result.rowcount or 0
        if count:
            log.warning(f"Revoked {count} keys for user {user_id[:8]}")
        return count

    # ------------------------------------------------------------------ #
    # Cleanup                                                            #
    # ------------------------------------------------------------------ #

    async def delete_expired(self, *, before: datetime | None = None) -> int:
        """Delete keys whose ``expires_at`` has passed.

        Intended for a periodic cron job. Returns number of rows deleted.
        Pass ``before`` to backdate (e.g. delete expired keys older than 30
        days for retention).
        """
        cutoff = before or datetime.now(timezone.utc)
        from sqlalchemy import delete as sa_delete

        result = await self._session.execute(
            sa_delete(ApiKey).where(
                ApiKey.expires_at.is_not(None),
                ApiKey.expires_at < cutoff,
            )
        )
        count = result.rowcount or 0
        if count:
            log.info(f"Deleted {count} expired API keys (cutoff={cutoff.isoformat()})")
        return count
