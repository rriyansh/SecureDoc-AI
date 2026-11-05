import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

def ingest_documents():
    # 1. Load all .txt files from the documents folder
    documents = []
    for filename in os.listdir("documents"):
        if filename.endswith(".txt"):
            loader = TextLoader(os.path.join("documents", filename))
            documents.extend(loader.load())

    if not documents:
        print("No documents found in the 'documents/' folder.")
        return

    # 2. Split documents into manageable chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    chunks = text_splitter.split_documents(documents)

    # 3. Create embeddings and store in FAISS
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(chunks, embeddings)

    # 4. Save the vector store locally
    vectorstore.save_local("vectorstore")
    print(f"Ingested {len(chunks)} chunks and saved to 'vectorstore/'.")

if __name__ == "__main__":
    ingest_documents()
