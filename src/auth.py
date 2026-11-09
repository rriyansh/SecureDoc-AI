"""Authentication: API keys and JWT token management."""

import os
import time
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from src.config import config
from src.logger import get_logger
from src.security import secret_manager

logger = get_logger(__name__)


@dataclass
class APIKey:
    """API Key data model."""
    key_id: str
    key_hash: str
    name: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class APIKeyManager:
    """Manage API keys with hashing and validation."""

    def __init__(self, storage_path: str = "./secrets/api_keys.json"):
        self.storage_path = storage_path
        self._keys: Dict[str, APIKey] = {}
        self._load_keys()

    def _load_keys(self) -> None:
        """Load API keys from storage."""
        import json
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                for item in data:
                    key = APIKey(
                        key_id=item["key_id"],
                        key_hash=item["key_hash"],
                        name=item["name"],
                        scopes=item["scopes"],
                        created_at=datetime.fromisoformat(item["created_at"]),
                        expires_at=datetime.fromisoformat(item["expires_at"]) if item.get("expires_at") else None,
                        last_used=datetime.fromisoformat(item["last_used"]) if item.get("last_used") else None,
                        is_active=item.get("is_active", True),
                        metadata=item.get("metadata", {}),
                    )
                    self._keys[key.key_id] = key
            except Exception as e:
                logger.error("Failed to load API keys: %s", e)

    def _save_keys(self) -> None:
        """Save API keys to storage."""
        import json
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        data = []
        for key in self._keys.values():
            data.append({
                "key_id": key.key_id,
                "key_hash": key.key_hash,
                "name": key.name,
                "scopes": key.scopes,
                "created_at": key.created_at.isoformat(),
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "last_used": key.last_used.isoformat() if key.last_used else None,
                "is_active": key.is_active,
                "metadata": key.metadata,
            })
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(self.storage_path, 0o600)

    def create_key(self, name: str, scopes: List[str], expires_days: Optional[int] = None) -> str:
        """Create a new API key and return the plaintext key."""
        key_id = secrets.token_urlsafe(16)
        plaintext_key = f"sk_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()

        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            scopes=scopes,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
        )
        self._keys[key_id] = api_key
        self._save_keys()
        logger.info("Created API key: %s (%s)", name, key_id)
        return plaintext_key

    def validate_key(self, plaintext_key: str) -> Optional[APIKey]:
        """Validate an API key and return the key metadata if valid."""
        key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
        for key in self._keys.values():
            if key.key_hash == key_hash and key.is_active:
                if key.expires_at and key.expires_at < datetime.utcnow():
                    logger.warning("API key expired: %s", key.key_id)
                    return None
                key.last_used = datetime.utcnow()
                self._save_keys()
                return key
        return None

    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        if key_id in self._keys:
            self._keys[key_id].is_active = False
            self._save_keys()
            logger.info("Revoked API key: %s", key_id)
            return True
        return False

    def list_keys(self) -> List[APIKey]:
        """List all API keys (without hashes)."""
        return list(self._keys.values())

    def get_key(self, key_id: str) -> Optional[APIKey]:
        """Get a specific API key by ID."""
        return self._keys.get(key_id)


@dataclass
class TokenPayload:
    """JWT token payload."""
    sub: str
    scopes: List[str]
    exp: int
    iat: int
    jti: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class JWTManager:
    """Manage JWT token creation and validation."""

    def __init__(self):
        self.secret = self._get_or_create_secret()
        self.algorithm = "HS256"
        self.default_ttl = 3600  # 1 hour

    def _get_or_create_secret(self) -> str:
        """Get or create JWT signing secret."""
        secret = secret_manager.load_secret("jwt_signing")
        if not secret:
            secret = secret_manager.generate_secret("jwt_signing", 64)
        return secret

    def create_token(self, subject: str, scopes: List[str], ttl: Optional[int] = None, metadata: Optional[Dict] = None) -> str:
        """Create a new JWT token."""
        now = int(time.time())
        ttl = ttl or self.default_ttl
        payload = TokenPayload(
            sub=subject,
            scopes=scopes,
            exp=now + ttl,
            iat=now,
            jti=secrets.token_urlsafe(16),
            metadata=metadata or {},
        )
        token = jwt.encode(payload.__dict__, self.secret, algorithm=self.algorithm)
        logger.debug("Created JWT for subject: %s", subject)
        return token

    def validate_token(self, token: str) -> Optional[TokenPayload]:
        """Validate a JWT token and return payload if valid."""
        try:
            decoded = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return TokenPayload(**decoded)
        except ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except InvalidTokenError as e:
            logger.warning("Invalid JWT token: %s", e)
            return None

    def refresh_token(self, token: str, ttl: Optional[int] = None) -> Optional[str]:
        """Refresh an existing valid token."""
        payload = self.validate_token(token)
        if not payload:
            return None
        return self.create_token(payload.sub, payload.scopes, ttl, payload.metadata)


api_key_manager = APIKeyManager()
jwt_manager = JWTManager()


def verify_api_key(api_key: str) -> Optional[APIKey]:
    """Convenience function to verify API key."""
    return api_key_manager.validate_key(api_key)


def verify_jwt_token(token: str) -> Optional[TokenPayload]:
    """Convenience function to verify JWT token."""
    return jwt_manager.validate_token(token)


def require_scopes(payload: TokenPayload, required_scopes: List[str]) -> bool:
    """Check if token payload has required scopes."""
    return all(scope in payload.scopes for scope in required_scopes)