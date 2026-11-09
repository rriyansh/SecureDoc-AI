"""Query API routes."""

from typing import Optional, List
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from api.dependencies import get_current_user, check_rate_limit, get_pipeline, CommonParams, require_scopes_dependency
from api.schemas import QueryRequest, QueryResponse, ErrorResponse
from src.rag_pipeline import SecureRAGPipeline
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Query the RAG pipeline",
    description="Submit a question to the SecureDoc AI RAG pipeline and receive an answer based on retrieved documents.",
)
async def query(
    request: Request,
    query_request: QueryRequest,
    params: CommonParams = Depends(),
    user: dict = Depends(check_rate_limit),
    pipeline: SecureRAGPipeline = Depends(get_pipeline),
) -> QueryResponse:
    """Process a query through the RAG pipeline."""
    request_id = getattr(request.state, "request_id", None)
    client_ip = request.client.host if request.client else None

    logger.info("Processing query from user=%s, ip=%s", user["user_id"], client_ip)

    try:
        answer = pipeline.query(
            question=query_request.question,
            user_id=user["user_id"],
            request_id=request_id,
            ip_address=client_ip,
            use_cache=params.use_cache,
            use_rewrite=params.use_rewrite,
        )

        return QueryResponse(
            answer=answer,
            request_id=request_id,
        )

    except Exception as e:
        logger.error("Query processing failed: %s", e)
        raise


@router.post(
    "/query/stream",
    summary="Stream query response",
    description="Stream the answer from the RAG pipeline (future implementation).",
)
async def query_stream(
    query_request: QueryRequest,
    user: dict = Depends(require_scopes_dependency(["query:stream"])),
) -> dict:
    """Stream query response (placeholder)."""
    return {"detail": "Streaming not yet implemented"}


class BatchQueryRequest(BaseModel):
    questions: List[str] = Field(..., min_items=1, max_items=10)
    use_cache: bool = True
    use_rewrite: bool = True


class BatchQueryResponse(BaseModel):
    results: List[QueryResponse]


@router.post(
    "/query/batch",
    response_model=BatchQueryResponse,
    summary="Batch query processing",
    description="Process multiple queries in a single request.",
)
async def query_batch(
    request: Request,
    batch_request: BatchQueryRequest,
    user: dict = Depends(check_rate_limit),
    pipeline: SecureRAGPipeline = Depends(get_pipeline),
) -> BatchQueryResponse:
    """Process multiple queries in batch."""
    request_id = getattr(request.state, "request_id", None)
    client_ip = request.client.host if request.client else None

    results = []
    for question in batch_request.questions:
        answer = pipeline.query(
            question=question,
            user_id=user["user_id"],
            request_id=request_id,
            ip_address=client_ip,
            use_cache=batch_request.use_cache,
            use_rewrite=batch_request.use_rewrite,
        )
        results.append(QueryResponse(answer=answer, request_id=request_id))

    return BatchQueryResponse(results=results)