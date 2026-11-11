"""Advanced, validated configuration with frozen settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Immutable, validated application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    # --- OpenAI ---
    openai_api_key: SecretStr = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
    openai_fallback_model: str = Field("gpt-4o-mini", alias="OPENAI_FALLBACK_MODEL")
    openai_embedding_model: str = Field("text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")

    # --- App ---
    app_name: str = Field("SecureDoc AI", alias="APP_NAME")
    app_version: str = Field("3.0.0", alias="APP_VERSION")
    environment: str = Field("production", alias="ENVIRONMENT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")
    debug: bool = Field(False, alias="DEBUG")

    # --- Auth ---
    api_keys: str = Field("", alias="API_KEYS")
    jwt_secret: SecretStr = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(60, alias="JWT_EXPIRE_MINUTES")
    jwt_issuer: str = Field("securedoc-ai", alias="JWT_ISSUER")
    admin_api_key: SecretStr = Field(..., alias="ADMIN_API_KEY")

    # --- Request signing ---
    request_signing_enabled: bool = Field(False, alias="REQUEST_SIGNING_ENABLED")
    request_signing_secret: SecretStr = Field(
        SecretStr(""), alias="REQUEST_SIGNING_SECRET"
    )
    request_signing_window_seconds: int = Field(300, alias="REQUEST_SIGNING_WINDOW_SECONDS")

    # --- Crypto ---
    cache_encryption_key: SecretStr = Field(
        SecretStr(""), alias="CACHE_ENCRYPTION_KEY"
    )
    cache_encrypt: bool = Field(True, alias="CACHE_ENCRYPT")

    # --- Paths ---
    vectorstore_path: Path = Field(Path("./vectorstore"), alias="VECTORSTORE_PATH")
    docstore_path: Path = Field(Path("./docstore"), alias="DOCSTORE_PATH")
    documents_path: Path = Field(Path("./documents"), alias="DOCUMENTS_PATH")
    config_path: Path = Field(Path("./config"), alias="CONFIG_PATH")
    audit_path: Path = Field(Path("./audit"), alias="AUDIT_PATH")

    # --- Retrieval ---
    child_chunk_size: int = Field(400, alias="CHILD_CHUNK_SIZE")
    child_chunk_overlap: int = Field(50, alias="CHILD_CHUNK_OVERLAP")
    parent_chunk_size: int = Field(2000, alias="PARENT_CHUNK_SIZE")
    parent_chunk_overlap: int = Field(200, alias="PARENT_CHUNK_OVERLAP")
    retriever_top_k: int = Field(10, alias="RETRIEVER_TOP_K")
    rerank_top_k: int = Field(4, alias="RERANK_TOP_K")
    bm25_weight: float = Field(0.4, alias="BM25_WEIGHT")
    vector_weight: float = Field(0.6, alias="VECTOR_WEIGHT")
    enable_reranker: bool = Field(True, alias="ENABLE_RERANKER")
    enable_query_rewrite: bool = Field(True, alias="ENABLE_QUERY_REWRITE")
    retriever_timeout_seconds: int = Field(15, alias="RETRIEVER_TIMEOUT_SECONDS")

    # --- Cache ---
    cache_enabled: bool = Field(True, alias="CACHE_ENABLED")
    cache_ttl_seconds: int = Field(3600, alias="CACHE_TTL_SECONDS")
    cache_max_size: int = Field(1000, alias="CACHE_MAX_SIZE")

    # --- Rate limit ---
    rate_limit_per_minute: int = Field(60, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_burst: int = Field(10, alias="RATE_LIMIT_BURST")
    rate_limit_strategy: str = Field("token_bucket", alias="RATE_LIMIT_STRATEGY")

    # --- Anomaly ---
    anomaly_detection_enabled: bool = Field(True, alias="ANOMALY_DETECTION_ENABLED")
    anomaly_threshold: int = Field(20, alias="ANOMALY_THRESHOLD")
    anomaly_window_seconds: int = Field(10, alias="ANOMALY_WINDOW_SECONDS")

    # --- Circuit breaker ---
    circuit_breaker_enabled: bool = Field(True, alias="CIRCUIT_BREAKER_ENABLED")
    circuit_breaker_fail_max: int = Field(5, alias="CIRCUIT_BREAKER_FAIL_MAX")
    circuit_breaker_reset_seconds: int = Field(60, alias="CIRCUIT_BREAKER_RESET_SECONDS")
    circuit_breaker_half_open_max: int = Field(2, alias="CIRCUIT_BREAKER_HALF_OPEN_MAX")

    # --- Dedup ---
    dedup_enabled: bool = Field(True, alias="DEDUP_ENABLED")
    dedup_window_seconds: int = Field(30, alias="DEDUP_WINDOW_SECONDS")

    # --- API ---
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")
    api_cors_origins: str = Field("*", alias="API_CORS_ORIGINS")
    api_max_request_size_mb: int = Field(10, alias="API_MAX_REQUEST_SIZE_MB")
    security_headers_enabled: bool = Field(True, alias="SECURITY_HEADERS_ENABLED")
    security_ip_allowlist: str = Field("", alias="SECURITY_IP_ALLOWLIST")

    # --- Audit ---
    audit_enabled: bool = Field(True, alias="AUDIT_ENABLED")
    audit_max_payload_chars: int = Field(500, alias="AUDIT_MAX_PAYLOAD_CHARS")
    audit_chain_hash: bool = Field(True, alias="AUDIT_CHAIN_HASH")

    # --- Metrics ---
    metrics_enabled: bool = Field(True, alias="METRICS_ENABLED")

    @field_validator("vectorstore_path", "docstore_path", "documents_path", "config_path", "audit_path")
    @classmethod
    def _expand(cls, v: Path) -> Path:
        return v.expanduser().resolve()

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        if len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        if self.request_signing_enabled and len(self.request_signing_secret.get_secret_value()) < 32:
            raise ValueError("REQUEST_SIGNING_SECRET required when signing enabled")
        if self.cache_encrypt and len(self.cache_encryption_key.get_secret_value()) < 32:
            raise ValueError("CACHE_ENCRYPTION_KEY required when cache_encrypt=true")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    @property
    def ip_allowlist(self) -> set[str]:
        return {ip.strip() for ip in self.security_ip_allowlist.split(",") if ip.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
