from langchain.vectorstores import FAISS
from langchain.retrievers import BM25Retriever, EnsembleRetriever
from langchain.embeddings import OpenAIEmbeddings


class HybridRetriever:
    def __init__(self, vectorstore_dir: str, embeddings=None, k: int = 4):
        self.vectorstore_dir = vectorstore_dir
        self.k = k
        self.embeddings = embeddings or OpenAIEmbeddings()

    def load(self, documents):
        vectorstore = FAISS.load_local(self.vectorstore_dir, self.embeddings)
        vector_retriever = vectorstore.as_retriever(search_kwargs={"k": self.k})
        bm25_retriever = BM25Retriever.from_documents(documents)
        bm25_retriever.k = self.k
        return EnsembleRetriever(
            retrievers=[bm25_retriever, vector_retriever],
            weights=[0.5, 0.5],
        )