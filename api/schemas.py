"""Request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    model_config = {
        "json_schema_extra": {"example": {"question": "How long is data retained?"}}
    }


class QueryResponse(BaseModel):
    question: str
    answer: str
    latency_ms: float
    cached: bool = False


class TokenRequest(BaseModel):
    api_key: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class StatsResponse(BaseModel):
    cache: dict
    rate_limiter: dict
