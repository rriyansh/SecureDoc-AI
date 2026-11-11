"""Request-scoped context variables for correlation IDs."""

from __future__ import annotations

import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
principal_var: contextvars.ContextVar[str] = contextvars.ContextVar("principal", default="")


def set_request_context(request_id: str, principal: str = "") -> None:
    request_id_var.set(request_id)
    principal_var.set(principal)


def current_request_id() -> str:
    return request_id_var.get()


def current_principal() -> str:
    return principal_var.get()
