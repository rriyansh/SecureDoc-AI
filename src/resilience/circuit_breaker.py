"""Circuit breaker for downstream dependency protection.

State machine
-------------
::

    CLOSED  ──failures >= fail_max──▶  OPEN
    OPEN    ──reset_seconds elapsed──▶  HALF_OPEN
    HALF_OPEN ──success──▶  CLOSED
    HALF_OPEN ──failure──▶  OPEN

Semantics
---------
* **CLOSED** — normal operation. Every failure increments the counter. When
  counter ≥ ``fail_max``, transition to OPEN.
* **OPEN** — all calls raise :class:`CircuitOpenError` immediately. This is
  the whole point: fast-fail without waiting for the slow dependency.
* **HALF_OPEN** — after ``reset_seconds``, the breaker allows up to
  ``half_open_max`` probe requests. Any success → CLOSED. Any failure → OPEN.

Concurrency
-----------
A single ``threading.Lock`` guards the state + counter. The lock is held only
for state-transition decisions (microseconds), **not** for the actual call —
so N concurrent calls all proceed in parallel when CLOSED.

Both sync and async callers are supported via ``call`` and ``acall``.
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any, Callable, Coroutine, TypeVar

from src.core.config import get_settings
from src.core.exceptions import CircuitOpenError
from src.core.logger import get_logger
from src.observability.metrics import CIRCUIT_OPEN

log = get_logger("resilience.circuit_breaker")

T = TypeVar("T")


class CircuitState(str, Enum):
    """Breaker state — string values are used in logs and metrics."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Concurrent circuit breaker with half-open probing."""

    def __init__(
        self,
        name: str,
        *,
        fail_max: int = 5,
        reset_seconds: int = 60,
        half_open_max: int = 2,
    ) -> None:
        if fail_max < 1:
            raise ValueError("fail_max must be >= 1")
        if reset_seconds < 1:
            raise ValueError("reset_seconds must be >= 1")
        if half_open_max < 1:
            raise ValueError("half_open_max must be >= 1")

        self.name = name
        self.fail_max = fail_max
        self.reset_seconds = reset_seconds
        self.half_open_max = half_open_max

        self._state: CircuitState = CircuitState.CLOSED
        self._failures = 0
        self._half_open_inflight = 0
        self._opened_at = 0.0  # monotonic timestamp when we transitioned to OPEN
        self._lock = threading.Lock()

        # Cumulative stats
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0
        self._total_rejections = 0

    # ------------------------------------------------------------------ #
    # Public accessors                                                   #
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> CircuitState:
        return self._state

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failures": self._failures,
                "total_calls": self._total_calls,
                "total_failures": self._total_failures,
                "total_successes": self._total_successes,
                "total_rejections": self._total_rejections,
                "fail_max": self.fail_max,
                "reset_seconds": self.reset_seconds,
            }

    def reset(self) -> None:
        """Force back to CLOSED — for tests and admin escape hatch."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._half_open_inflight = 0
            self._opened_at = 0.0
        log.info(f"Circuit [{self.name}] manually reset → CLOSED")

    # ------------------------------------------------------------------ #
    # State transitions (must hold lock)                                 #
    # ------------------------------------------------------------------ #

    def _try_admit(self) -> None:
        """Decide whether to admit a call. Raises ``CircuitOpenError`` on reject.

        Called under lock. Handles time-based OPEN→HALF_OPEN transition.
        """
        self._total_calls += 1

        if self._state == CircuitState.CLOSED:
            return

        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.reset_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_inflight = 0
                log.info(f"Circuit [{self.name}] → HALF_OPEN after {elapsed:.1f}s")
            else:
                self._total_rejections += 1
                retry_after = int(self.reset_seconds - elapsed) + 1
                raise CircuitOpenError(
                    f"Circuit [{self.name}] is OPEN "
                    f"(retry in {retry_after}s)",
                    retry_after=retry_after,
                )

        # HALF_OPEN — allow limited probes
        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_inflight >= self.half_open_max:
                self._total_rejections += 1
                raise CircuitOpenError(
                    f"Circuit [{self.name}] HALF_OPEN probe budget exhausted",
                    retry_after=self.reset_seconds,
                )
            self._half_open_inflight += 1

    def _on_success(self) -> None:
        """Record success and close if in HALF_OPEN. Caller holds lock."""
        self._total_successes += 1
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._half_open_inflight = 0
            log.info(f"Circuit [{self.name}] → CLOSED (probe succeeded)")

    def _on_failure(self) -> None:
        """Record failure and open if threshold met. Caller holds lock."""
        self._total_failures += 1
        self._failures += 1
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._half_open_inflight = 0
            CIRCUIT_OPEN.labels(name=self.name).inc()
            log.warning(f"Circuit [{self.name}] HALF_OPEN probe failed → OPEN")
            return
        if self._failures >= self.fail_max:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            CIRCUIT_OPEN.labels(name=self.name).inc()
            log.warning(
                f"Circuit [{self.name}] → OPEN "
                f"(failures={self._failures}/{self.fail_max})"
            )

    # ------------------------------------------------------------------ #
    # Sync call                                                          #
    # ------------------------------------------------------------------ #

    def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute ``fn(*args, **kwargs)`` through the breaker.

        Raises
        ------
        CircuitOpenError
            If the circuit is currently OPEN or HALF_OPEN budget exhausted.
        Exception
            Any exception raised by ``fn`` — re-raised after state update.
        """
        with self._lock:
            self._try_admit()

        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._on_failure()
            raise

        with self._lock:
            self._on_success()
        return result

    # ------------------------------------------------------------------ #
    # Async call                                                         #
    # ------------------------------------------------------------------ #

    async def acall(
        self,
        fn: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Async variant of :meth:`call`."""
        with self._lock:
            self._try_admit()

        try:
            result = await fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._on_failure()
            raise

        with self._lock:
            self._on_success()
        return result


# --------------------------------------------------------------------------- #
# Singleton for LLM calls                                                      #
# --------------------------------------------------------------------------- #

_llm_breaker: CircuitBreaker | None = None


def get_llm_breaker() -> CircuitBreaker:
    """Return the process-wide LLM circuit breaker (built once)."""
    global _llm_breaker
    if _llm_breaker is None:
        s = get_settings()
        _llm_breaker = CircuitBreaker(
            "llm",
            fail_max=s.circuit_breaker_fail_max,
            reset_seconds=s.circuit_breaker_reset_seconds,
            half_open_max=s.circuit_breaker_half_open_max,
        )
        log.info(
            f"LLM circuit breaker initialized "
            f"(fail_max={s.circuit_breaker_fail_max}, "
            f"reset={s.circuit_breaker_reset_seconds}s, "
            f"half_open_max={s.circuit_breaker_half_open_max})"
        )
    return _llm_breaker
