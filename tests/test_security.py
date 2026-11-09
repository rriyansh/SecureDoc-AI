"""Tests for security module."""

import pytest
from src.security import (
    detect_pii,
    redact_pii,
    sanitize_input,
    sanitize_dict,
    SecretManager,
    verify_webhook_signature,
)
import os
import tempfile


class TestDetectPII:
    def test_detect_email(self):
        text = "Contact me at user@example.com"
        findings = detect_pii(text)
        assert any(f["type"] == "email" for f in findings)
        assert any(f["value"] == "user@example.com" for f in findings)

    def test_detect_phone(self):
        text = "Call 555-123-4567"
        findings = detect_pii(text)
        assert any(f["type"] == "phone" for f in findings)

    def test_detect_ssn(self):
        text = "SSN: 123-45-6789"
        findings = detect_pii(text)
        assert any(f["type"] == "ssn" for f in findings)

    def test_detect_credit_card(self):
        text = "Card: 4111-1111-1111-1111"
        findings = detect_pii(text)
        assert any(f["type"] == "credit_card" for f in findings)

    def test_detect_api_key(self):
        text = "sk_test_abcdefghijklmnopqrstuvwxyz123456"
        findings = detect_pii(text)
        assert any(f["type"] == "api_key" for f in findings)

    def test_detect_aws_key(self):
        text = "AKIAIOSFODNN7EXAMPLE"
        findings = detect_pii(text)
        assert any(f["type"] == "aws_access_key" for f in findings)

    def test_detect_jwt(self):
        text = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        findings = detect_pii(text)
        assert any(f["type"] == "jwt" for f in findings)

    def test_no_pii(self):
        text = "This is a normal sentence without sensitive data."
        findings = detect_pii(text)
        assert len(findings) == 0


class TestRedactPII:
    def test_redact_email(self):
        text = "Email: user@example.com"
        redacted = redact_pii(text)
        assert "user@example.com" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_multiple(self):
        text = "Email: user@example.com, Phone: 555-123-4567"
        redacted = redact_pii(text)
        assert "user@example.com" not in redacted
        assert "555-123-4567" not in redacted
        assert redacted.count("[REDACTED]") == 2

    def test_custom_replacement(self):
        text = "Email: user@example.com"
        redacted = redact_pii(text, replacement="***")
        assert "***" in redacted


class TestSanitizeInput:
    def test_sanitize_normal(self):
        text = "Hello world"
        assert sanitize_input(text) == "Hello world"

    def test_sanitize_trim(self):
        text = "  hello  "
        assert sanitize_input(text) == "hello"

    def test_sanitize_control_chars(self):
        text = "hello\x00world\x1f"
        assert sanitize_input(text) == "helloworld"

    def test_sanitize_newlines_preserved(self):
        text = "hello\nworld\r\ntest"
        result = sanitize_input(text)
        assert "\n" in result
        assert "\r" in result

    def test_sanitize_max_length(self):
        text = "a" * 3000
        result = sanitize_input(text, max_length=100)
        assert len(result) == 100

    def test_sanitize_empty(self):
        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""


class TestSanitizeDict:
    def test_sanitize_simple(self):
        data = {"name": "John", "password": "secret123"}
        result = sanitize_dict(data)
        assert result["name"] == "John"
        assert result["password"] == "[REDACTED]"

    def test_sanitize_nested(self):
        data = {"user": {"password": "secret", "email": "user@test.com"}}
        result = sanitize_dict(data)
        assert result["user"]["password"] == "[REDACTED]"
        assert result["user"]["email"] == "user@test.com"

    def test_sanitize_list(self):
        data = {"items": [{"token": "abc"}, {"token": "def"}]}
        result = sanitize_dict(data)
        assert result["items"][0]["token"] == "[REDACTED]"
        assert result["items"][1]["token"] == "[REDACTED]"

    def test_sanitize_string_values(self):
        data = {"query": "  hello world  "}
        result = sanitize_dict(data)
        assert result["query"] == "hello world"


class TestSecretManager:
    def test_generate_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SecretManager(secret_dir=tmpdir)
            secret = manager.generate_secret("test_key")
            loaded = manager.load_secret("test_key")
            assert loaded == secret

    def test_rotate_secret(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SecretManager(secret_dir=tmpdir)
            secret1 = manager.generate_secret("rotate_key")
            secret2 = manager.rotate_secret("rotate_key")
            assert secret1 != secret2
            loaded = manager.load_secret("rotate_key")
            assert loaded == secret2

    def test_hash_secret(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SecretManager(secret_dir=tmpdir)
            secret = "test_secret"
            hashed = manager.hash_secret(secret)
            assert len(hashed) == 64  # SHA256 hex


class TestVerifyWebhookSignature:
    def test_valid_signature(self):
        payload = b'{"event": "test"}'
        secret = "webhook_secret"
        import hmac
        import hashlib
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(payload, signature, secret)

    def test_invalid_signature(self):
        payload = b'{"event": "test"}'
        assert not verify_webhook_signature(payload, "invalid", "secret")