"""Application configuration loader."""

import os
from typing import Any, Dict

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
    def embedding_model(self) -> str:
        return os.getenv("EMBEDDING_MODEL", self.get("embedding.model", "text-embedding-3-small"))

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


config = Config()
