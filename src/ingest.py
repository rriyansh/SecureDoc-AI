import os
from dotenv import load_dotenv

from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

load_dotenv()

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "documents")
VECTORSTORE_DIR = os.path.join(os.path.dirname(__file__), "..", "vectorstore")
EMBEDDING_MODEL = "text-embedding-ada-002"


def load_documents(documents_dir: str = DOCUMENTS_DIR):
    loader = DirectoryLoader(documents_dir, glob="**/*.txt", loader_cls=TextLoader)
    return loader.load()


def chunk_documents(documents, chunk_size: int = 500, chunk_overlap: int = 50):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    return splitter.split_documents(documents)


def build_vectorstore(chunks, embedding_model: str = EMBEDDING_MODEL):
    embeddings = OpenAIEmbeddings(model=embedding_model)
    return FAISS.from_documents(chunks, embeddings)


def ingest(documents_dir: str = DOCUMENTS_DIR, vectorstore_dir: str = VECTORSTORE_DIR):
    documents = load_documents(documents_dir)
    chunks = chunk_documents(documents)
    vectorstore = build_vectorstore(chunks)
    vectorstore.save_local(vectorstore_dir)
    print(f"Ingested {len(chunks)} chunks into {vectorstore_dir}")


if __name__ == "__main__":
    ingest()