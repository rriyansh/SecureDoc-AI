"""Configuration management.

Single source of truth for every environment variable in the application.
Loaded once at startup via ``get_settings()`` (cached), validated eagerly, and
exposed as an immutable :class:`Settings` object.

Security guarantees
-------------------
* Secret values use :class:`pydantic.SecretStr` — never accidentally logged.
* Startup validation rejects weak/short secrets, mismatched toggles, and
  missing dependencies between flags (e.g. signing enabled without secret).
* Unknown env vars are ignored (``extra="ignore"``) to allow forward-compat.

Usage
-----
>>> from src.core.config import get_settings
>>> s = get_settings()
>>> s.environment
'production'
>>> s.openai_api_key.get_secret_value()  # explicit opt-in
'sk-...'
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import (
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

Environment = Literal["development", "staging", "production", "test"]
LogFormat = Literal["json", "text"]
RateLimitStrategy = Literal["token_bucket", "sliding_window"]

_MIN_SECRET_KEY_LEN = 64
_MIN_ENCRYPTION_KEY_LEN = 32
_MIN_SIGNING_KEY_LEN = 32
_MIN_OPENAI_KEY_LEN = 20
_MIN_DB_URL_LEN = 10


def _is_url(value: str, schemes: tuple[str, ...]) -> bool:
    """Return True if value is a valid URL with one of the allowed schemes."""
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in schemes and bool(parsed.netloc)


def _normalize_path(raw: str | Path) -> Path:
    """Expand ``~`` and resolve to an absolute path."""
    return Path(raw).expanduser().resolve()


def _csv_to_list(raw: str) -> list[str]:
    """Split a comma-separated env var into a clean list."""
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------- #
# Settings                                                                     #
# --------------------------------------------------------------------------- #

class Settings(BaseSettings):
    """Immutable application configuration.

    Loaded from environment + ``.env`` file. Validated at construction. Once
    created, no field can be reassigned (``frozen=True``) — mutations must go
    through a process restart, which is the correct safety property for a
    server-side service.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    # ====================================================================== #
    # 1. Application identity                                                #
    # ====================================================================== #
    app_name: str = Field("SecureDoc AI", alias="APP_NAME")
    app_version: str = Field("4.0.0", alias="APP_VERSION")
    environment: Environment = Field("development", alias="ENVIRONMENT")
    debug: bool = Field(False, alias="DEBUG")
    secret_key: SecretStr = Field(..., alias="SECRET_KEY")

    # ====================================================================== #
    # 2. OpenAI                                                              #
    # ====================================================================== #
    openai_api_key: SecretStr = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
    openai_fallback_model: str = Field("gpt-4o-mini", alias="OPENAI_FALLBACK_MODEL")
    openai_embedding_model: str = Field(
        "text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )
    openai_timeout_seconds: int = Field(30, alias="OPENAI_TIMEOUT_SECONDS", ge=5, le=120)

    # ====================================================================== #
    # 3. PostgreSQL                                                          #
    # ====================================================================== #
    database_url: str = Field(..., alias="DATABASE_URL")
    database_pool_size: int = Field(10, alias="DATABASE_POOL_SIZE", ge=1, le=100)
    database_max_overflow: int = Field(20, alias="DATABASE_MAX_OVERFLOW", ge=0, le=200)
    database_pool_timeout: int = Field(30, alias="DATABASE_POOL_TIMEOUT", ge=1, le=300)
    database_echo: bool = Field(False, alias="DATABASE_ECHO")

    # ====================================================================== #
    # 4. Redis (optional)                                                    #
    # ====================================================================== #
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    redis_enabled: bool = Field(False, alias="REDIS_ENABLED")
    redis_socket_timeout: int = Field(2, alias="REDIS_SOCKET_TIMEOUT", ge=1, le=30)

    # ====================================================================== #
    # 5. JWT                                                                 #
    # ====================================================================== #
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = Field(
        "HS256", alias="JWT_ALGORITHM"
    )
    jwt_expire_minutes: int = Field(60, alias="JWT_EXPIRE_MINUTES", ge=5, le=1440)
    jwt_issuer: str = Field("securedoc-ai", alias="JWT_ISSUER")
    jwt_audience: str = Field("securedoc-api", alias="JWT_AUDIENCE")

    # ====================================================================== #
    # 6. Bootstrap admin                                                     #
    # ====================================================================== #
    bootstrap_admin_email: str = Field(
        "admin@example.com", alias="BOOTSTRAP_ADMIN_EMAIL"
    )
    bootstrap_admin_password: SecretStr = Field(
        SecretStr("change-me-immediately-123"), alias="BOOTSTRAP_ADMIN_PASSWORD"
    )

    # ====================================================================== #
    # 7. Request signing (defense-in-depth)                                  #
    # ====================================================================== #
    request_signing_enabled: bool = Field(False, alias="REQUEST_SIGNING_ENABLED")
    request_signing_secret: SecretStr = Field(
        SecretStr(""), alias="REQUEST_SIGNING_SECRET"
    )
    request_signing_window_seconds: int = Field(
        300, alias="REQUEST_SIGNING_WINDOW_SECONDS", ge=30, le=3600
    )

    # ====================================================================== #
    # 8. Response cache                                                      #
    # ====================================================================== #
    cache_enabled: bool = Field(True, alias="CACHE_ENABLED")
    cache_ttl_seconds: int = Field(3600, alias="CACHE_TTL_SECONDS", ge=1, le=86400)
    cache_max_size: int = Field(1000, alias="CACHE_MAX_SIZE", ge=1, le=1_000_000)
    cache_encrypt: bool = Field(True, alias="CACHE_ENCRYPT")
    cache_encryption_key: SecretStr = Field(
        SecretStr(""), alias="CACHE_ENCRYPTION_KEY"
    )
    cache_namespace: str = Field("securedoc:v4", alias="CACHE_NAMESPACE")

    # ====================================================================== #
    # 9. Rate limiting                                                       #
    # ====================================================================== #
    rate_limit_per_minute: int = Field(60, alias="RATE_LIMIT_PER_MINUTE", ge=1, le=10000)
    rate_limit_burst: int = Field(10, alias="RATE_LIMIT_BURST", ge=1, le=1000)
    rate_limit_strategy: RateLimitStrategy = Field(
        "token_bucket", alias="RATE_LIMIT_STRATEGY"
    )

    # ====================================================================== #
    # 10. Anomaly detection                                                  #
    # ====================================================================== #
    anomaly_detection_enabled: bool = Field(True, alias="ANOMALY_DETECTION_ENABLED")
    anomaly_threshold: int = Field(20, alias="ANOMALY_THRESHOLD", ge=1, le=1000)
    anomaly_window_seconds: int = Field(10, alias="ANOMALY_WINDOW_SECONDS", ge=1, le=600)

    # ====================================================================== #
    # 11. Circuit breaker                                                    #
    # ====================================================================== #
    circuit_breaker_enabled: bool = Field(True, alias="CIRCUIT_BREAKER_ENABLED")
    circuit_breaker_fail_max: int = Field(5, alias="CIRCUIT_BREAKER_FAIL_MAX", ge=1, le=100)
    circuit_breaker_reset_seconds: int = Field(
        60, alias="CIRCUIT_BREAKER_RESET_SECONDS", ge=5, le=3600
    )
    circuit_breaker_half_open_max: int = Field(
        2, alias="CIRCUIT_BREAKER_HALF_OPEN_MAX", ge=1, le=10
    )

    # ====================================================================== #
    # 12. Deduplication                                                      #
    # ====================================================================== #
    dedup_enabled: bool = Field(True, alias="DEDUP_ENABLED")
    dedup_window_seconds: int = Field(30, alias="DEDUP_WINDOW_SECONDS", ge=1, le=600)

    # ====================================================================== #
    # 13. Filesystem paths                                                   #
    # ====================================================================== #
    vectorstore_path: Path = Field(Path("./vectorstore"), alias="VECTORSTORE_PATH")
    docstore_path: Path = Field(Path("./docstore"), alias="DOCSTORE_PATH")
    documents_path: Path = Field(Path("./documents"), alias="DOCUMENTS_PATH")
    config_path: Path = Field(Path("./config"), alias="CONFIG_PATH")
    logs_path: Path = Field(Path("./logs"), alias="LOGS_PATH")

    # ====================================================================== #
    # 14. RAG pipeline                                                       #
    # ====================================================================== #
    child_chunk_size: int = Field(400, alias="CHILD_CHUNK_SIZE", ge=100, le=2000)
    child_chunk_overlap: int = Field(50, alias="CHILD_CHUNK_OVERLAP", ge=0, le=500)
    parent_chunk_size: int = Field(2000, alias="PARENT_CHUNK_SIZE", ge=500, le=10000)
    parent_chunk_overlap: int = Field(200, alias="PARENT_CHUNK_OVERLAP", ge=0, le=1000)
    retriever_top_k: int = Field(10, alias="RETRIEVER_TOP_K", ge=1, le=50)
    rerank_top_k: int = Field(4, alias="RERANK_TOP_K", ge=1, le=20)
    bm25_weight: float = Field(0.4, alias="BM25_WEIGHT", ge=0.0, le=1.0)
    vector_weight: float = Field(0.6, alias="VECTOR_WEIGHT", ge=0.0, le=1.0)
    enable_reranker: bool = Field(True, alias="ENABLE_RERANKER")
    enable_query_rewrite: bool = Field(True, alias="ENABLE_QUERY_REWRITE")

    # ====================================================================== #
    # 15. HTTP API                                                           #
    # ====================================================================== #
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT", ge=1, le=65535)
    api_cors_origins: str = Field("*", alias="API_CORS_ORIGINS")
    api_max_request_size_mb: int = Field(10, alias="API_MAX_REQUEST_SIZE_MB", ge=1, le=100)
    security_headers_enabled: bool = Field(True, alias="SECURITY_HEADERS_ENABLED")
    security_ip_allowlist: str = Field("", alias="SECURITY_IP_ALLOWLIST")
    admin_ui_enabled: bool = Field(True, alias="ADMIN_UI_ENABLED")

    # ====================================================================== #
    # 16. Logging                                                            #
    # ====================================================================== #
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: LogFormat = Field("json", alias="LOG_FORMAT")

    # ====================================================================== #
    # Field validators                                                       #
    # ====================================================================== #

    @field_validator(
        "vectorstore_path",
        "docstore_path",
        "documents_path",
        "config_path",
        "logs_path",
        mode="after",
    )
    @classmethod
    def _expand_paths(cls, v: Path) -> Path:
        return _normalize_path(v)

    @field_validator("log_level", mode="after")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(
                f"LOG_LEVEL must be one of {sorted(allowed)}, got {v!r}"
            )
        return upper

    @field_validator("database_url", mode="after")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        if len(v) < _MIN_DB_URL_LEN:
            raise ValueError("DATABASE_URL appears too short")
        # Must be an async driver — app is fully async
        if not v.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
            raise ValueError(
                "DATABASE_URL must use an async driver "
                "(postgresql+asyncpg:// or sqlite+aiosqlite://)"
            )
        return v

    @field_validator("redis_url", mode="after")
    @classmethod
    def _validate_redis_url(cls, v: str) -> str:
        if not _is_url(v, ("redis", "rediss")):
            raise ValueError(f"REDIS_URL must be redis:// or rediss://, got {v!r}")
        return v

    @field_validator("api_cors_origins", mode="after")
    @classmethod
    def _validate_cors(cls, v: str) -> str:
        # Reject wildcard with credentials risk — but allow explicit "*" for dev.
        # Production should set explicit origins; app enforces this separately.
        return v

    # ====================================================================== #
    # Model (cross-field) validators                                         #
    # ====================================================================== #

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        """Fail fast on weak or missing secrets."""
        sk = self.secret_key.get_secret_value()
        if len(sk) < _MIN_SECRET_KEY_LEN:
            raise ValueError(
                f"SECRET_KEY must be at least {_MIN_SECRET_KEY_LEN} characters "
                f"(got {len(sk)}). Generate with: openssl rand -hex 32"
            )

        oai = self.openai_api_key.get_secret_value()
        if not oai.startswith("sk-") or len(oai) < _MIN_OPENAI_KEY_LEN:
            raise ValueError(
                "OPENAI_API_KEY must start with 'sk-' and be at least "
                f"{_MIN_OPENAI_KEY_LEN} chars"
            )

        if self.cache_encrypt:
            ck = self.cache_encryption_key.get_secret_value()
            if len(ck) < _MIN_ENCRYPTION_KEY_LEN:
                raise ValueError(
                    f"CACHE_ENCRYPTION_KEY must be at least "
                    f"{_MIN_ENCRYPTION_KEY_LEN} chars when CACHE_ENCRYPT=true"
                )

        if self.request_signing_enabled:
            ss = self.request_signing_secret.get_secret_value()
            if len(ss) < _MIN_SIGNING_KEY_LEN:
                raise ValueError(
                    f"REQUEST_SIGNING_SECRET must be at least "
                    f"{_MIN_SIGNING_KEY_LEN} chars when REQUEST_SIGNING_ENABLED=true"
                )

        # Child chunks must be <= parent chunks (invariant)
        if self.child_chunk_size > self.parent_chunk_size:
            raise ValueError(
                "CHILD_CHUNK_SIZE must be <= PARENT_CHUNK_SIZE "
                f"({self.child_chunk_size} > {self.parent_chunk_size})"
            )

        # Weights must sum to 1.0 (allow tiny float error)
        total_w = self.bm25_weight + self.vector_weight
        if not (0.99 <= total_w <= 1.01):
            raise ValueError(
                f"BM25_WEIGHT + VECTOR_WEIGHT must equal 1.0, got {total_w:.3f}"
            )

        # Rate-limit burst must be sensible
        if self.rate_limit_burst > self.rate_limit_per_minute * 10:
            raise ValueError(
                "RATE_LIMIT_BURST is absurdly larger than "
                "RATE_LIMIT_PER_MINUTE — check your config"
            )

        # Production must not run with DEBUG=true
        if self.environment == "production" and self.debug:
            raise ValueError(
                "DEBUG must be false in production"
            )

        # Production must not use wildcard CORS
        if self.environment == "production" and "*" in _csv_to_list(self.api_cors_origins):
            raise ValueError(
                "API_CORS_ORIGINS cannot contain '*' in production"
            )

        return self

    # ====================================================================== #
    # Computed properties                                                    #
    # ====================================================================== #

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return _csv_to_list(self.api_cors_origins)

    @property
    def ip_allowlist(self) -> set[str]:
        return set(_csv_to_list(self.security_ip_allowlist))

    @property
    def allowlist_enabled(self) -> bool:
        return bool(self.security_ip_allowlist.strip())

    @property
    def cache_backend(self) -> Literal["redis", "memory"]:
        return "redis" if self.redis_enabled else "memory"

    @property
    def openai_configured(self) -> bool:
        return len(self.openai_api_key.get_secret_value()) >= _MIN_OPENAI_KEY_LEN

    @property
    def redis_configured(self) -> bool:
        return self.redis_enabled and _is_url(self.redis_url, ("redis", "rediss"))

    # ====================================================================== #
    # Introspection                                                          #
    # ====================================================================== #

    def safe_dict(self) -> dict[str, Any]:
        """Return a dict safe for logging — all secrets redacted."""
        data = self.model_dump()
        redacted: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, dict) and "__secret__" in str(value):
                redacted[key] = "***redacted***"
            elif any(
                marker in key.lower()
                for marker in ("key", "secret", "password", "token", "dsn")
            ):
                redacted[key] = "***redacted***"
            else:
                redacted[key] = str(value) if isinstance(value, Path) else value
        return redacted


# --------------------------------------------------------------------------- #
# Singleton accessor                                                           #
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached :class:`Settings` instance.

    The cache can be cleared in tests via ``get_settings.cache_clear()``.
    """
    # Allow test overrides of env-file path
    _env_file = os.environ.get("SECUREDOC_ENV_FILE")
    if _env_file:
        return Settings(_env_file=_env_file)  # type: ignore[call-arg]
    return Settings()  # type: ignore[call-arg]
