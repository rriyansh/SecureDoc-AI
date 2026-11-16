"""Async SQLAlchemy engine, session factory, and lifecycle helpers.

Design decisions
----------------
1. **One engine per process.** The engine holds a connection pool that must be
   shared across requests. Creating a new engine per request would defeat
   pooling.

2. **``expire_on_commit=False``.** This is mandatory in async SQLAlchemy. If a
   session expires attributes after ``commit()``, the next attribute access
   triggers a lazy load — which in async context raises ``MissingGreenlet``.
   Setting this to ``False`` means we must not rely on a fresh read after
   commit; we hold onto the already-loaded values instead.

3. **Retry only at the scope level, not per-request.** For FastAPI requests,
   ``get_db`` yields a session; if the DB connection drops mid-request the
   exception propagates (500/503) — retrying a half-completed transaction is
   risky. For background scripts, ``session_scope`` retries the entire unit
   of work with exponential backoff.

4. **``pool_pre_ping=True``.** Each connection is validated before use. Solves
   the classic "server closed the connection unexpectedly" after Postgres
   recycles idle connections.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import get_settings
from src.core.logger import get_logger

log = get_logger("db.session")


# --------------------------------------------------------------------------- #
# Engine construction                                                          #
# --------------------------------------------------------------------------- #

def _build_engine() -> AsyncEngine:
    """Create the process-wide async engine.

    Configuration is pulled from :func:`get_settings` once at import time.
    This means the engine is bound to whatever env was present at startup —
    correct for a 12-factor app.
    """
    s = get_settings()

    # SQLite (used in tests) rejects pool_size / max_overflow — must special-case.
    is_sqlite = s.database_url.startswith("sqlite")
    pool_kwargs: dict[str, Any] = {}
    if not is_sqlite:
        pool_kwargs = {
            "pool_size": s.database_pool_size,
            "max_overflow": s.database_max_overflow,
            "pool_timeout": s.database_pool_timeout,
            "pool_recycle": 1800,  # Recycle every 30 min — well below typical pg timeout
        }

    engine = create_async_engine(
        s.database_url,
        echo=s.database_echo,
        pool_pre_ping=True,
        future=True,
        **pool_kwargs,
    )
    log.info(
        f"Async engine created "
        f"(driver={s.database_url.split('://')[0]}, "
        f"pool_size={s.database_pool_size if not is_sqlite else 'n/a'})"
    )
    return engine


engine: AsyncEngine = _build_engine()


# --------------------------------------------------------------------------- #
# Session factory                                                              #
# --------------------------------------------------------------------------- #

SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # See module docstring — mandatory for async
    autoflush=False,         # Flush happens explicitly where needed
    autobegin=True,
)


# --------------------------------------------------------------------------- #
# FastAPI dependency                                                           #
# --------------------------------------------------------------------------- #

async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yield a session bound to the request lifecycle.

    * On success: caller must call ``await session.commit()`` explicitly.
      Returning the response without a commit means the transaction is
      rolled back on session close (safe default — no accidental writes).
    * On exception: rollback, then re-raise.

    Do **not** commit here — routes need fine-grained control over transaction
    boundaries (e.g. commit after the RAG answer has been computed so we don't
    hold a row lock during an LLM call).
    """
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# --------------------------------------------------------------------------- #
# Scripts / background tasks: session with retry                               #
# --------------------------------------------------------------------------- #

# Only retry on transient connection errors — not on integrity or syntax errors.
_TRANSIENT_ERRORS = (OperationalError, DBAPIError)


def _is_transient(exc: BaseException) -> bool:
    """Filter DBAPIError — only retry on lost connections."""
    if isinstance(exc, OperationalError):
        return True
    if isinstance(exc, DBAPIError):
        return bool(getattr(exc, "connection_invalidated", False))
    return False


@asynccontextmanager
async def session_scope(
    *,
    retries: int = 3,
    backoff_seconds: float = 0.5,
) -> AsyncIterator[AsyncSession]:
    """Context-managed transaction with retry — for scripts, tests, workers.

    Example
    -------
    >>> async with session_scope() as session:
    ...     repo = UserRepository(session)
    ...     user = await repo.create("a@b.com", "hashed")
    ...     # auto-commits on clean exit
    """
    attempt = 0
    last_exc: BaseException | None = None

    while attempt < retries:
        attempt += 1
        async with SessionFactory() as session:
            try:
                yield session
                await session.commit()
                return
            except _TRANSIENT_ERRORS as exc:
                if not _is_transient(exc):
                    await session.rollback()
                    raise
                await session.rollback()
                last_exc = exc
                delay = backoff_seconds * (2 ** (attempt - 1))
                log.warning(
                    f"Transient DB error (attempt {attempt}/{retries}): "
                    f"{type(exc).__name__} — retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
                continue
            except Exception:
                await session.rollback()
                raise

    # All attempts failed
    log.error(f"DB operation failed after {retries} attempts")
    assert last_exc is not None
    raise last_exc


# --------------------------------------------------------------------------- #
# Health check                                                                 #
# --------------------------------------------------------------------------- #

async def healthcheck(timeout_seconds: float = 2.0) -> dict[str, Any]:
    """Lightweight DB health probe — used by ``/health/deps``."""
    try:
        async with asyncio.timeout(timeout_seconds):
            async with SessionFactory() as session:
                await session.execute(text("SELECT 1"))
        return {"name": "postgres", "healthy": True}
    except Exception as exc:
        log.warning(f"DB healthcheck failed: {exc}")
        return {
            "name": "postgres",
            "healthy": False,
            "error": type(exc).__name__,
        }


# --------------------------------------------------------------------------- #
# Shutdown                                                                     #
# --------------------------------------------------------------------------- #

async def dispose_engine() -> None:
    """Dispose the engine and close all pooled connections.

    Called from FastAPI's lifespan shutdown hook — ensures clean shutdown
    and prevents connection leaks in container restarts.
    """
    await engine.dispose()
    log.info("DB engine disposed.")
