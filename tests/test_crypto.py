"""Tests for src.crypto."""

import pytest

from src import crypto


def test_encrypt_decrypt(monkeypatch):
    monkeypatch.setenv("CACHE_ENCRYPTION_KEY", "a" * 32)
    from src.config import get_settings
    get_settings.cache_clear()
    plaintext = "secret message"
    blob = crypto.encrypt(plaintext)
    assert blob != plaintext
    assert crypto.decrypt(blob) == plaintext


def test_tamper_detection(monkeypatch):
    monkeypatch.setenv("CACHE_ENCRYPTION_KEY", "a" * 32)
    from src.config import get_settings
    get_settings.cache_clear()
    blob = crypto.encrypt("msg")
    tampered = blob[:-4] + "AAAA"
    with pytest.raises(Exception):
        crypto.decrypt(tampered)
