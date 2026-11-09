"""API request/response schemas."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="The question to ask")
    use_cache: bool = Field(True, description="Whether to use cache")
    use_rewrite: bool = Field(True, description="Whether to rewrite query for better retrieval")
    top_k: Optional[int] = Field(None, ge=1, le=50, description="Number of results to retrieve")

    @validator("question")
    def validate_question(cls, v):
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()


class QueryResponse(BaseModel):
    answer: str
    request_id: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    detail: str
    request_id: Optional[str] = None
    error_code: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    checks: Dict[str, Any]


class ReadinessResponse(BaseModel):
    ready: bool
    checks: Dict[str, bool]


class IngestRequest(BaseModel):
    doc_dir: str = Field("documents", description="Directory containing documents")
    user_id: str = Field("system", description="User initiating ingestion")


class IngestResponse(BaseModel):
    documents_processed: int
    chunks_created: int
    duration_ms: float
    errors: List[str] = Field(default_factory=list)
    request_id: Optional[str] = None


class EvaluationRequest(BaseModel):
    dataset_path: Optional[str] = Field(None, description="Path to evaluation dataset")
    output_path: Optional[str] = Field(None, description="Path to save results")


class EvaluationResponse(BaseModel):
    status: str
    dataset: str
    num_samples: int
    metrics: Dict[str, float]
    duration_seconds: float


class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = Field(default_factory=list)
    expires_days: Optional[int] = Field(None, ge=1, le=365)


class APIKeyCreateResponse(BaseModel):
    key_id: str
    name: str
    scopes: List[str]
    plaintext_key: str
    created_at: str
    expires_at: Optional[str] = None


class APIKeyInfo(BaseModel):
    key_id: str
    name: str
    scopes: List[str]
    created_at: str
    expires_at: Optional[str] = None
    last_used: Optional[str] = None
    is_active: bool


class APIKeyListResponse(BaseModel):
    keys: List[APIKeyInfo]


class CacheStatsResponse(BaseModel):
    exact: Dict[str, Any]
    semantic: Dict[str, Any]


class RateLimitInfo(BaseModel):
    limit: int
    remaining: int
    reset_at: int


class ConfigResponse(BaseModel):
    config: Dict[str, Any]


class BatchQueryRequest(BaseModel):
    questions: List[str] = Field(..., min_items=1, max_items=10)
    use_cache: bool = True
    use_rewrite: bool = True


class BatchQueryResponse(BaseModel):
    results: List[QueryResponse]


class DocumentChunk(BaseModel):
    text: str
    metadata: Dict[str, Any]
    score: Optional[float] = None


class RetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: Optional[int] = Field(None, ge=1, le=50)
    use_rerank: bool = True


class RetrievalResponse(BaseModel):
    results: List[DocumentChunk]
    query: str
    total_results: int
    duration_ms: float