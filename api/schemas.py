"""Pydantic schemas with strict validation."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def _no_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question cannot be blank")
        return v

    model_config = {
        "json_schema_extra": {"example": {"question": "How long is data retained?"}}
    }


class QueryResponse(BaseModel):
    question: str
    answer: str
    latency_ms: float
    cached: bool = False
    request_id: str = ""


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


class DepsResponse(BaseModel):
    healthy: bool
    checks: list[dict]


class StatsResponse(BaseModel):
    cache: dict
    rate_limiter: dict
    circuit_breaker: dict
    dedup: dict


class ErrorResponse(BaseModel):
    error: str
    code: str
    request_id: str = ""
