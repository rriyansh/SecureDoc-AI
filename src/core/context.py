"""Request-scoped context variables.

FastAPI is async and handles many requests concurrently on the same event
loop. Thread-local storage is wrong; ``contextvars`` is right — it propagates
through async boundaries automatically.

Populate context at the start of each request (middleware) and read it from
anywhere downstream (handlers, repositories, log filters).

Public API
----------
>>> set_request_context(request_id="abc", principal="key:xx", user_id="u1")
>>> current_request_id()
'abc'
>>> current_principal()
'key:xx'

>>> with request_context(request_id="tmp", principal="test"):
...     ...
"""

from __future__ import annotations

import contextlib
import contextvars
import uuid
from contextvars import ContextVar, Token
from typing import Iterator


# --------------------------------------------------------------------------- #
# Context variables                                                            #
# --------------------------------------------------------------------------- #

_request_id: ContextVar[str] = ContextVar("request_id", default="")
_principal: ContextVar[str] = ContextVar("principal", default="")
_user_id: ContextVar[str] = ContextVar("user_id", default="")
_path: ContextVar[str] = ContextVar("path", default="")


# --------------------------------------------------------------------------- #
# Setters                                                                      #
# --------------------------------------------------------------------------- #

def set_request_context(
    request_id: str,
    principal: str = "",
    user_id: str = "",
    path: str = "",
) -> None:
    """Set all context vars for the current task."""
    _request_id.set(request_id)
    _principal.set(principal)
    _user_id.set(user_id)
    _path.set(path)


def clear_request_context() -> None:
    """Reset all context vars (call at end of request if needed)."""
    _request_id.set("")
    _principal.set("")
    _user_id.set("")
    _path.set("")


def new_request_id() -> str:
    """Generate a fresh UUID4 request ID."""
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# Getters                                                                      #
# --------------------------------------------------------------------------- #

def current_request_id() -> str:
    return _request_id.get()


def current_principal() -> str:
    return _principal.get()


def current_user_id() -> str:
    return _user_id.get()


def current_path() -> str:
    return _path.get()


def current_context() -> dict[str, str]:
    """Snapshot of all context values — useful for structured logging."""
    return {
        "request_id": _request_id.get(),
        "principal": _principal.get(),
        "user_id": _user_id.get(),
        "path": _path.get(),
    }


# --------------------------------------------------------------------------- #
# Context manager (for tests and scripts)                                      #
# --------------------------------------------------------------------------- #

@contextlib.contextmanager
def request_context(
    request_id: str | None = None,
    principal: str = "",
    user_id: str = "",
    path: str = "",
) -> Iterator[dict[str, str]]:
    """Temporarily set request context within a ``with`` block."""
    tokens: list[Token[object]] = [
        _request_id.set(request_id or new_request_id()),
        _principal.set(principal),
        _user_id.set(user_id),
        _path.set(path),
    ]
    try:
        yield current_context()
    finally:
        # Restore in reverse order
        _path.reset(tokens[3])
        _user_id.reset(tokens[2])
        _principal.reset(tokens[1])
        _request_id.reset(tokens[0])
