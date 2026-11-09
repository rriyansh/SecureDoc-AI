"""Application configuration loader."""

import os
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized configuration accessor."""

    def __init__(self, config_path: str = "config/config.yml"):
        self.config_path = config_path
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            return {}
        with open(self.config_path, "r") as fh:
            return yaml.safe_load(fh) or {}

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        node: Any = self._data
        for part in keys:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def models(self) -> list:
        return self.get("models", [])

    @property
    def openai_model(self) -> str:
        return os.getenv("OPENAI_MODEL", self.get("models.0.model", "gpt-4o-mini"))

    @property
    def openai_api_key(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def openai_temperature(self) -> float:
        return float(os.getenv("OPENAI_TEMPERATURE", self.get("models.0.temperature", 0.1)))

    @property
    def openai_max_tokens(self) -> int:
        return int(os.getenv("OPENAI_MAX_TOKENS", self.get("models.0.max_tokens", 1024)))

    @property
    def embedding_model(self) -> str:
        return os.getenv("EMBEDDING_MODEL", self.get("embedding.model", "text-embedding-3-small"))

    @property
    def embedding_dimension(self) -> int:
        return int(os.getenv("VECTOR_DIM", self.get("embedding.dimension", 1536)))

    @property
    def embedding_batch_size(self) -> int:
        return int(os.getenv("EMBEDDING_BATCH_SIZE", self.get("embedding.batch_size", 100)))

    @property
    def chunk_size(self) -> int:
        return int(os.getenv("CHUNK_SIZE", self.get("chunking.chunk_size", 512)))

    @property
    def chunk_overlap(self) -> int:
        return int(os.getenv("CHUNK_OVERLAP", self.get("chunking.chunk_overlap", 50)))

    @property
    def top_k(self) -> int:
        return int(os.getenv("TOP_K", self.get("retrieval.top_k", 5)))

    @property
    def rerank_top_k(self) -> int:
        return int(os.getenv("RERANK_TOP_K", self.get("retrieval.rerank_top_k", 25)))

    @property
    def hybrid_alpha(self) -> float:
        return float(os.getenv("HYBRID_ALPHA", self.get("retrieval.hybrid_alpha", 0.5)))

    @property
    def qdrant_host(self) -> str:
        return os.getenv("QDRANT_HOST", self.get("vectorstore.host", "localhost"))

    @property
    def qdrant_port(self) -> int:
        return int(os.getenv("QDRANT_PORT", self.get("vectorstore.port", 6333)))

    @property
    def qdrant_collection(self) -> str:
        return os.getenv("QDRANT_COLLECTION", self.get("vectorstore.collection", "secure_docs"))

    @property
    def vector_dim(self) -> int:
        return int(os.getenv("VECTOR_DIM", self.get("embedding.dimension", 1536)))

    @property
    def vectorstore_provider(self) -> str:
        return os.getenv("VECTORSTORE_PROVIDER", self.get("vectorstore.provider", "qdrant"))

    @property
    def docstore_path(self) -> str:
        return os.getenv("DOCSTORE_PATH", self.get("docstore.path", "./docstore"))

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def api_host(self) -> str:
        return os.getenv("API_HOST", "0.0.0.0")

    @property
    def api_port(self) -> int:
        return int(os.getenv("API_PORT", 8000))

    @property
    def api_workers(self) -> int:
        return int(os.getenv("API_WORKERS", 4))

    @property
    def guardrails_config_path(self) -> str:
        return os.getenv("GUARDRAILS_CONFIG_PATH", "./config/rails")

    @property
    def input_rails_enabled(self) -> bool:
        return os.getenv("INPUT_RAILS_ENABLED", "true").lower() == "true"

    @property
    def output_rails_enabled(self) -> bool:
        return os.getenv("OUTPUT_RAILS_ENABLED", "true").lower() == "true"

    @property
    def eval_dataset_path(self) -> str:
        return os.getenv("EVAL_DATASET_PATH", "./tests/eval_dataset.json")

    @property
    def ragas_metrics(self) -> List[str]:
        metrics_str = os.getenv("RAGAS_METRICS", "faithfulness,answer_relevancy,context_precision,context_recall")
        return [m.strip() for m in metrics_str.split(",")]

    @property
    def rate_limit_default_capacity(self) -> int:
        return int(os.getenv("RATE_LIMIT_CAPACITY", 100))

    @property
    def rate_limit_default_refill(self) -> float:
        return float(os.getenv("RATE_LIMIT_REFILL", 10.0))

    @property
    def query_rate_limit_capacity(self) -> int:
        return int(os.getenv("QUERY_RATE_LIMIT_CAPACITY", 20))

    @property
    def query_rate_limit_refill(self) -> float:
        return float(os.getenv("QUERY_RATE_LIMIT_REFILL", 2.0))

    @property
    def cache_exact_max_size(self) -> int:
        return int(os.getenv("CACHE_EXACT_MAX_SIZE", 1000))

    @property
    def cache_semantic_max_size(self) -> int:
        return int(os.getenv("CACHE_SEMANTIC_MAX_SIZE", 500))

    @property
    def cache_similarity_threshold(self) -> float:
        return float(os.getenv("CACHE_SIMILARITY_THRESHOLD", 0.85))

    @property
    def cache_ttl(self) -> int:
        return int(os.getenv("CACHE_TTL", 3600))

    @property
    def audit_log_dir(self) -> str:
        return os.getenv("AUDIT_LOG_DIR", "./audit")

    @property
    def audit_max_file_size(self) -> int:
        return int(os.getenv("AUDIT_MAX_FILE_SIZE", 100 * 1024 * 1024))

    @property
    def audit_max_files(self) -> int:
        return int(os.getenv("AUDIT_MAX_FILES", 10))

    @property
    def secret_dir(self) -> str:
        return os.getenv("SECRET_DIR", "./secrets")

    @property
    def cross_encoder_model(self) -> str:
        return os.getenv("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")


config = Config()