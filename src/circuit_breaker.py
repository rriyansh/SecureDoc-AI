"""Circuit breaker for resilience."""

from __future__ import annotations

import threading
import time
from enum import Enum

from src.config import get_settings
from src.exceptions import CircuitOpenError
from src.logger import get_logger

log = get_logger("circuit_breaker")


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, name: str, fail_max: int, reset_seconds: int, half_open_max: int) -> None:
        self.name = name
        self.fail_max = fail_max
        self.reset_seconds = reset_seconds
        self.half_open_max = half_open_max
        self._state = State.CLOSED
        self._failures = 0
        self._half_open_calls = 0
        self._opened_at = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> State:
        return self._state

    def _can_attempt(self) -> bool:
        if self._state == State.CLOSED:
            return True
        if self._state == State.OPEN:
            if time.monotonic() - self._opened_at >= self.reset_seconds:
                self._state = State.HALF_OPEN
                self._half_open_calls = 0
                log.info(f"Breaker [{self.name}] → HALF_OPEN")
                return True
            return False
        # HALF_OPEN
        if self._half_open_calls < self.half_open_max:
            self._half_open_calls += 1
            return True
        return False

    def _record_success(self) -> None:
        if self._state == State.HALF_OPEN:
            self._state = State.CLOSED
            self._failures = 0
            self._half_open_calls = 0
            log.info(f"Breaker [{self.name}] → CLOSED")

    def _record_failure(self) -> None:
        self._failures += 1
        if self._state == State.HALF_OPEN or self._failures >= self.fail_max:
            self._state = State.OPEN
            self._opened_at = time.monotonic()
            log.warning(f"Breaker [{self.name}] → OPEN (failures={self._failures})")

    def call(self, fn, *args, **kwargs):
        with self._lock:
            if not self._can_attempt():
                raise CircuitOpenError(f"Circuit [{self.name}] is open")
        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._record_failure()
            raise
        with self._lock:
            self._record_success()
        return result

    def stats(self) -> dict[str, object]:
        return {
            "name": self.name,
            "state": self._state.value,
            "failures": self._failures,
        }


_llm_breaker: CircuitBreaker | None = None


def get_llm_breaker() -> CircuitBreaker:
    global _llm_breaker
    if _llm_breaker is None:
        s = get_settings()
        _llm_breaker = CircuitBreaker(
            name="llm",
            fail_max=s.circuit_breaker_fail_max,
            reset_seconds=s.circuit_breaker_reset_seconds,
            half_open_max=s.circuit_breaker_half_open_max,
        )
    return _llm_breaker
