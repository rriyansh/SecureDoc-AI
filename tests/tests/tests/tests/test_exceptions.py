"""Tests for exceptions."""

from src.exceptions import (
    AuthenticationError,
    CircuitOpenError,
    PipelineError,
    SecureDocError,
)


def test_defaults():
    assert SecureDocError("x").status_code == 500
    assert AuthenticationError("x").status_code == 401
    assert CircuitOpenError("x").status_code == 503
    assert PipelineError("x").code == "pipeline_error"
