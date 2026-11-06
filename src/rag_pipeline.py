"""RAG pipeline orchestrating ingest, retrieve, and generate."""

from typing import List

from src.config import config
from src.hybrid_retriever import HybridRetriever, RetrievalResult
from src.logger import get_logger

logger = get_logger(__name__)


class SecureRAGPipeline:
    def __init__(self):
        self.retriever = HybridRetriever()

    def retrieve(self, query: str) -> List[RetrievalResult]:
        return self.retriever.retrieve(query)

    def query(self, question: str) -> str:
        """Answer a question through the RAG pipeline."""
        results = self.retrieve(question)
        if not results:
            return "I could not find relevant information in the documents."
        context = "\n\n".join(r.text for r in results[: config.top_k])
        answer = self._generate(question, context)
        return answer

    def _generate(self, question: str, context: str) -> str:
        """Placeholder LLM generation step."""
        return (
            f"Based on the retrieved context:\n{context}\n\n"
            f"Answer to '{question}': (LLM generation placeholder)"
        )
