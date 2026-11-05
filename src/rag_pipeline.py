import os
from dotenv import load_dotenv

from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA

load_dotenv()

VECTORSTORE_DIR = os.path.join(os.path.dirname(__file__), "..", "vectorstore")
EMBEDDING_MODEL = "text-embedding-ada-002"
LLM_MODEL = "gpt-3.5-turbo"


def get_vectorstore(vectorstore_dir: str = VECTORSTORE_DIR):
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    return FAISS.load_local(vectorstore_dir, embeddings)


def get_qa_chain(vectorstore_dir: str = VECTORSTORE_DIR, model: str = LLM_MODEL):
    vectorstore = get_vectorstore(vectorstore_dir)
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 4})
    llm = ChatOpenAI(model=model, temperature=0.1)
    return RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)


def answer(query: str, vectorstore_dir: str = VECTORSTORE_DIR, model: str = LLM_MODEL):
    qa = get_qa_chain(vectorstore_dir, model)
    return qa.run(query)


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "What is the document retention policy?"
    print(answer(query))