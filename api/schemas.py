"""Pydantic request/response schemas."""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="User question")

    model_config = {
        "json_schema_extra": {
            "example": {"question": "How long is customer data retained?"}
        }
    }


class QueryResponse(BaseModel):
    question: str
    answer: str
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
