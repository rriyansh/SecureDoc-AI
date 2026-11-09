"""Tests for auth module."""

import pytest
import time
from src.auth import (
    APIKeyManager,
    JWTManager,
    verify_api_key,
    verify_jwt_token,
    require_scopes,
    APIKey,
    TokenPayload,
)


class TestAPIKeyManager:
    def test_create_key(self):
        manager = APIKeyManager(storage_path=":memory:")
        key = manager.create_key("Test Key", ["read", "write"])
        assert key.startswith("sk_")
        assert len(key) > 30

    def test_validate_key(self):
        manager = APIKeyManager(storage_path=":memory:")
        plaintext = manager.create_key("Test Key", ["read"])
        api_key = manager.validate_key(plaintext)
        assert api_key is not None
        assert api_key.name == "Test Key"
        assert api_key.scopes == ["read"]

    def test_validate_invalid_key(self):
        manager = APIKeyManager(storage_path=":memory:")
        assert manager.validate_key("sk_invalid") is None

    def test_revoke_key(self):
        manager = APIKeyManager(storage_path=":memory:")
        plaintext = manager.create_key("Test Key", ["read"])
        api_key = manager.validate_key(plaintext)
        key_id = api_key.key_id

        assert manager.revoke_key(key_id) is True
        assert manager.validate_key(plaintext) is None
        assert manager.revoke_key(key_id) is False

    def test_list_keys(self):
        manager = APIKeyManager(storage_path=":memory:")
        manager.create_key("Key 1", ["read"])
        manager.create_key("Key 2", ["write"])

        keys = manager.list_keys()
        assert len(keys) == 2

    def test_get_key(self):
        manager = APIKeyManager(storage_path=":memory:")
        plaintext = manager.create_key("Test Key", ["read"])
        api_key = manager.validate_key(plaintext)

        retrieved = manager.get_key(api_key.key_id)
        assert retrieved is not None
        assert retrieved.key_id == api_key.key_id

    def test_expired_key(self):
        manager = APIKeyManager(storage_path=":memory:")
        # Create key that expires in the past
        plaintext = manager.create_key("Expired Key", ["read"], expires_days=-1)
        assert manager.validate_key(plaintext) is None


class TestJWTManager:
    def test_create_token(self):
        manager = JWTManager()
        token = manager.create_token("user123", ["read", "write"])
        assert token.count(".") == 2  # JWT has 3 parts

    def test_validate_token(self):
        manager = JWTManager()
        token = manager.create_token("user123", ["read"])
        payload = manager.validate_token(token)
        assert payload is not None
        assert payload.sub == "user123"
        assert payload.scopes == ["read"]

    def test_validate_invalid_token(self):
        manager = JWTManager()
        assert manager.validate_token("invalid.token.here") is None

    def test_expired_token(self):
        manager = JWTManager()
        token = manager.create_token("user123", ["read"], ttl=-1)  # Expired
        time.sleep(0.01)
        assert manager.validate_token(token) is None

    def test_refresh_token(self):
        manager = JWTManager()
        token = manager.create_token("user123", ["read"])
        new_token = manager.refresh_token(token)
        assert new_token != token
        payload = manager.validate_token(new_token)
        assert payload.sub == "user123"

    def test_refresh_invalid_token(self):
        manager = JWTManager()
        assert manager.refresh_token("invalid") is None


class TestRequireScopes:
    def test_has_required_scopes(self):
        payload = TokenPayload(
            sub="user123",
            scopes=["read", "write", "admin"],
            exp=9999999999,
            iat=0,
            jti="test",
        )
        assert require_scopes(payload, ["read"]) is True
        assert require_scopes(payload, ["read", "write"]) is True

    def test_missing_scope(self):
        payload = TokenPayload(
            sub="user123",
            scopes=["read"],
            exp=9999999999,
            iat=0,
            jti="test",
        )
        assert require_scopes(payload, ["write"]) is False
        assert require_scopes(payload, ["read", "write"]) is False

    def test_empty_required(self):
        payload = TokenPayload(
            sub="user123",
            scopes=["read"],
            exp=9999999999,
            iat=0,
            jti="test",
        )
        assert require_scopes(payload, []) is True


class TestConvenienceFunctions:
    def test_verify_api_key(self):
        from src.auth import api_key_manager
        plaintext = api_key_manager.create_key("Test", ["read"])
        result = verify_api_key(plaintext)
        assert result is not None

    def test_verify_jwt_token(self):
        from src.auth import jwt_manager
        token = jwt_manager.create_token("user123", ["read"])
        result = verify_jwt_token(token)
        assert result is not None
        assert result.sub == "user123"