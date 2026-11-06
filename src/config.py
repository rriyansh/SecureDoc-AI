"""Centralised configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- OpenAI ---
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(
        "text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )

    # --- App ---
    app_name: str = Field("SecureDoc AI", alias="APP_NAME")
    app_version: str = Field("1.0.0", alias="APP_VERSION")
    environment: str = Field("production", alias="ENVIRONMENT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # --- Paths ---
    vectorstore_path: Path = Field(Path("./vectorstore"), alias="VECTORSTORE_PATH")
    docstore_path: Path = Field(Path("./docstore"), alias="DOCSTORE_PATH")
    documents_path: Path = Field(Path("./documents"), alias="DOCUMENTS_PATH")
    config_path: Path = Field(Path("./config"), alias="CONFIG_PATH")

    # --- Retrieval ---
    child_chunk_size: int = Field(400, alias="CHILD_CHUNK_SIZE")
    child_chunk_overlap: int = Field(50, alias="CHILD_CHUNK_OVERLAP")
    parent_chunk_size: int = Field(2000, alias="PARENT_CHUNK_SIZE")
    parent_chunk_overlap: int = Field(200, alias="PARENT_CHUNK_OVERLAP")
    retriever_top_k: int = Field(4, alias="RETRIEVER_TOP_K")
    bm25_weight: float = Field(0.4, alias="BM25_WEIGHT")
    vector_weight: float = Field(0.6, alias="VECTOR_WEIGHT")

    # --- API ---
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")
    api_cors_origins: str = Field("*", alias="API_CORS_ORIGINS")
    api_rate_limit: int = Field(60, alias="API_RATE_LIMIT")

    @field_validator("vectorstore_path", "docstore_path", "documents_path", "config_path")
    @classmethod
    def ensure_path(cls, v: Path) -> Path:
        return v.expanduser().resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()  # type: ignore[call-arg]
