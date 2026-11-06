from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="SecureDoc-AI Enhanced API")


class QueryRequest(BaseModel):
    question: str


async def stream_answer(question: str):
    yield f"data: Processing question: {question}\n\n"
    yield f"data: Answer placeholder for '{question}'\n\n"


@app.post("/query")
async def query(request: QueryRequest):
    return StreamingResponse(stream_answer(request.question), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}