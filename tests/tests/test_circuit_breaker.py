"""Tests for circuit breaker."""

from src.circuit_breaker import CircuitBreaker, State
from src.exceptions import CircuitOpenError


def test_closed_passes():
    cb = CircuitBreaker("t", fail_max=3, reset_seconds=1, half_open_max=2)
    assert cb.call(lambda: 42) == 42
    assert cb.state == State.CLOSED


def test_opens_after_failures():
    cb = CircuitBreaker("t2", fail_max=2, reset_seconds=1, half_open_max=1)

    def boom():
        raise RuntimeError("fail")

    for _ in range(2):
        try:
            cb.call(boom)
        except RuntimeError:
            pass
    assert cb.state == State.OPEN
    try:
        cb.call(lambda: 1)
    except CircuitOpenError:
        pass
