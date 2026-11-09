"""Security utilities: PII detection, input sanitization, secrets management."""

import os
import re
import hashlib
import secrets
from typing import Dict, List, Optional, Set
from functools import lru_cache

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


PII_PATTERNS: Dict[str, re.Pattern] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "api_key": re.compile(r"\b(?:sk|pk|api)[-_]?[A-Za-z0-9]{20,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b"),
}

SENSITIVE_KEYS: Set[str] = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "private_key",
    "client_secret",
    "auth",
    "authorization",
    "credential",
}


def detect_pii(text: str) -> List[Dict[str, str]]:
    """Detect PII in text and return list of findings."""
    findings = []
    for pii_type, pattern in PII_PATTERNS.items():
        for match in pattern.finditer(text):
            findings.append({
                "type": pii_type,
                "value": match.group(),
                "start": match.start(),
                "end": match.end(),
            })
    return findings


def redact_pii(text: str, replacement: str = "[REDACTED]") -> str:
    """Redact PII from text."""
    result = text
    for pii_type, pattern in PII_PATTERNS.items():
        result = pattern.sub(replacement, result)
    return result


def sanitize_input(text: str, max_length: int = 2000) -> str:
    """Sanitize user input: trim, limit length, remove control chars."""
    if not text:
        return ""
    sanitized = "".join(char for char in text if ord(char) >= 32 or char in "\n\r\t")
    sanitized = sanitized.strip()
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
        logger.warning("Input truncated to %d characters", max_length)
    return sanitized


def sanitize_dict(data: Dict, sensitive_keys: Optional[Set[str]] = None) -> Dict:
    """Recursively sanitize dictionary, redacting sensitive keys."""
    sensitive = sensitive_keys or SENSITIVE_KEYS
    result = {}
    for key, value in data.items():
        if key.lower() in sensitive:
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, sensitive)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item, sensitive) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str):
            result[key] = sanitize_input(value)
        else:
            result[key] = value
    return result


class SecretManager:
    """Manage secrets with rotation support."""

    def __init__(self, secret_dir: str = "./secrets"):
        self.secret_dir = secret_dir
        os.makedirs(secret_dir, exist_ok=True)

    def generate_secret(self, name: str, length: int = 32) -> str:
        """Generate a new cryptographically secure secret."""
        secret = secrets.token_urlsafe(length)
        self.store_secret(name, secret)
        return secret

    def store_secret(self, name: str, secret: str) -> None:
        """Store secret to file with restricted permissions."""
        path = os.path.join(self.secret_dir, f"{name}.secret")
        with open(path, "w") as f:
            f.write(secret)
        os.chmod(path, 0o600)
        logger.info("Stored secret: %s", name)

    def load_secret(self, name: str) -> Optional[str]:
        """Load secret from file."""
        path = os.path.join(self.secret_dir, f"{name}.secret")
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return f.read().strip()

    def rotate_secret(self, name: str, length: int = 32) -> str:
        """Rotate a secret: generate new, archive old."""
        old_secret = self.load_secret(name)
        if old_secret:
            archive_path = os.path.join(self.secret_dir, f"{name}.secret.bak")
            with open(archive_path, "w") as f:
                f.write(old_secret)
            os.chmod(archive_path, 0o600)
        return self.generate_secret(name, length)

    def hash_secret(self, secret: str) -> str:
        """Return SHA256 hash of secret for verification."""
        return hashlib.sha256(secret.encode()).hexdigest()


secret_manager = SecretManager()


@lru_cache(maxsize=128)
def get_cached_secret(name: str) -> Optional[str]:
    """Cached secret lookup for performance."""
    return secret_manager.load_secret(name)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC signature for webhook payloads."""
    import hmac
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)