import os
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA
from nemoguardrails import RailsConfig, LLMRails

load_dotenv()

class SecureRAGPipeline:
    def __init__(self):
        # Load the vector store
        embeddings = OpenAIEmbeddings()
        self.vectorstore = FAISS.load_local(
            "vectorstore", 
            embeddings, 
            allow_dangerous_deserialization=True
        )
        self.retriever = self.vectorstore.as_retriever()

        # Initialize the LLM
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        # Set up the standard RAG chain
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.retriever
        )

        # Load NeMo Guardrails configuration
        config = RailsConfig.from_path("./config")
        self.guarded_rails = LLMRails(config)

    def query(self, user_question: str) -> str:
        # First, run the input through guardrails
        guard_response = self.guarded_rails.generate(messages=[{
            "role": "user",
            "content": user_question
        }])

        # If the guardrail blocked the request, return its message
        if "I cannot comply" in guard_response["content"]:
            return guard_response["content"]

        # Otherwise, proceed with the standard RAG pipeline
        rag_result = self.qa_chain.invoke({"query": user_question})
        return rag_result["result"]
