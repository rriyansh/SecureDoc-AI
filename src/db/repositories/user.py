"""User data access.

Responsibilities
----------------
* CRUD on :class:`User`
* Pagination (limit/offset with count)
* Search by email substring (admin dashboard)
* Soft state transitions (activate, deactivate, promote)

Non-responsibilities
--------------------
* Password hashing — caller passes ``password_hash`` already computed
* Token issuance — done in the auth layer
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.db.models import User

log = get_logger("db.repositories.user")


class UserRepository:
    """Query facade for the ``users`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ #
    # Lookups                                                            #
    # ------------------------------------------------------------------ #

    async def get_by_id(self, user_id: str) -> User | None:
        """Return the user with the given UUID, or ``None``."""
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Return the user with the given email (case-insensitive).

        Emails are stored lowercased on create, so the comparison is
        consistent — no ``func.lower()`` needed, index is used.
        """
        result = await self._session.execute(
            select(User).where(User.email == email.strip().lower())
        )
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        """True if a user with the given email already exists."""
        result = await self._session.execute(
            select(func.count())
            .select_from(User)
            .where(User.email == email.strip().lower())
        )
        return (result.scalar() or 0) > 0

    # ------------------------------------------------------------------ #
    # Create                                                             #
    # ------------------------------------------------------------------ #

    async def create(
        self,
        email: str,
        password_hash: str,
        *,
        is_admin: bool = False,
        is_active: bool = True,
    ) -> User:
        """Insert a new user and return it (flushed, not committed).

        Raises
        ------
        ValueError
            If the email is empty or already registered.
        """
        normalised = email.strip().lower()
        if not normalised or "@" not in normalised:
            raise ValueError(f"Invalid email: {email!r}")

        # Check before insert — the unique index is a safety net, but this
        # gives a clean error instead of an IntegrityError.
        if await self.exists_by_email(normalised):
            raise ValueError(f"Email already registered: {normalised}")

        user = User(
            email=normalised,
            password_hash=password_hash,
            is_active=is_active,
            is_admin=is_admin,
        )
        self._session.add(user)
        await self._session.flush()  # assign id + timestamps via DB defaults
        await self._session.refresh(user)  # load server-side defaults
        log.info(f"User created: {user.id[:8]} ({normalised})")
        return user

    # ------------------------------------------------------------------ #
    # Listing / pagination                                               #
    # ------------------------------------------------------------------ #

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        include_inactive: bool = False,
    ) -> list[User]:
        """Paginated list, newest first."""
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        stmt = select(User).order_by(User.created_at.desc())
        if not include_inactive:
            stmt = stmt.where(User.is_active.is_(True))
        stmt = stmt.limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, *, include_inactive: bool = False) -> int:
        """Total count of users (respecting the same filter as ``list``)."""
        stmt = select(func.count()).select_from(User)
        if not include_inactive:
            stmt = stmt.where(User.is_active.is_(True))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def search_by_email(
        self, substring: str, *, limit: int = 50
    ) -> list[User]:
        """Case-insensitive substring search (admin dashboard)."""
        query = f"%{substring.strip().lower()}%"
        stmt = (
            select(User)
            .where(User.email.ilike(query))
            .order_by(User.created_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------ #
    # Mutations                                                          #
    # ------------------------------------------------------------------ #

    async def set_active(self, user_id: str, active: bool) -> bool:
        """Enable/disable a user. Returns True if the user existed."""
        user = await self.get_by_id(user_id)
        if user is None:
            return False
        user.is_active = active
        await self._session.flush()
        log.info(f"User {user_id[:8]} active={active}")
        return True

    async def set_admin(self, user_id: str, admin: bool) -> bool:
        """Grant/revoke admin. Returns True if the user existed."""
        user = await self.get_by_id(user_id)
        if user is None:
            return False
        user.is_admin = admin
        await self._session.flush()
        log.info(f"User {user_id[:8]} admin={admin}")
        return True

    async def update_password_hash(self, user_id: str, new_hash: str) -> bool:
        """Rotate a user's password hash (caller hashes plaintext)."""
        user = await self.get_by_id(user_id)
        if user is None:
            return False
        user.password_hash = new_hash
        await self._session.flush()
        log.info(f"User {user_id[:8]} password rotated")
        return True
