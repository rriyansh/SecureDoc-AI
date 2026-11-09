"""Tests for src.auth."""

import pytest
from fastapi import HTTPException

from src.auth import (
    create_access_token, decode_access_token, hash_secret,
    verify_admin_key, verify_api_key, verify_secret,
)


def test_api_key_ok():
    assert verify_api_key("test-api-key-1").startswith("key:")


def test_api_key_missing():
    with pytest.raises(HTTPException) as e:
        verify_api_key(None)
    assert e.value.status_code == 401


def test_api_key_invalid():
    with pytest.raises(HTTPException):
        verify_api_key("wrong")


def test_admin_ok():
    assert verify_admin_key("test-admin-key") == "admin"


def test_admin_fail():
    with pytest.raises(HTTPException):
        verify_admin_key("nope")


def test_jwt_round_trip():
    token = create_access_token("alice")
    assert decode_access_token(token)["sub"] == "alice"


def test_hash_verify():
    h = hash_secret("hunter2")
    assert verify_secret("hunter2", h)
    assert not verify_secret("wrong", h)
