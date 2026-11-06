"""FastAPI application entry point."""

from fastapi import FastAPI

from api.schemas import QueryRequest, QueryResponse
from api.middleware import SecurityMiddleware
from src.rag_pipeline import SecureRAGPipeline

app = FastAPI(title="SecureDoc AI", version="0.1.0")

app.add_middleware(SecurityMiddleware)

pipeline = SecureRAGPipeline()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    answer = pipeline.query(request.question)
    return QueryResponse(answer=answer)
