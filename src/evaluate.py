import os
from dotenv import load_dotenv

from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA

from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision

load_dotenv()

VECTORSTORE_DIR = os.path.join(os.path.dirname(__file__), "..", "vectorstore")
EMBEDDING_MODEL = "text-embedding-ada-002"
LLM_MODEL = "gpt-3.5-turbo"


EVAL_DATA = [
    {
        "question": "What is the document retention policy?",
        "ground_truth": "Documents are retained for a period of 7 years unless otherwise specified by legal requirements.",
    },
    {
        "question": "Is multi-factor authentication required?",
        "ground_truth": "Yes, multi-factor authentication is required for all users accessing the document management system.",
    },
]


def run_evaluation(vectorstore_dir: str = VECTORSTORE_DIR, model: str = LLM_MODEL):
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = FAISS.load_local(vectorstore_dir, embeddings)
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 4})
    llm = ChatOpenAI(model=model, temperature=0.1)
    qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)

    results = []
    for item in EVAL_DATA:
        answer_text = qa.run(item["question"])
        results.append(
            {
                "question": item["question"],
                "answer": answer_text,
                "contexts": [doc.page_content for doc in retriever.get_relevant_documents(item["question"])],
                "ground_truth": item["ground_truth"],
            }
        )

    dataset = {
        "question": [r["question"] for r in results],
        "answer": [r["answer"] for r in results],
        "contexts": [r["contexts"] for r in results],
        "ground_truth": [r["ground_truth"] for r in results],
    }

    score = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
    )
    print(score)
    return score


if __name__ == "__main__":
    run_evaluation()