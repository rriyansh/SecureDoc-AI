import os
from dotenv import load_dotenv
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from src.rag_pipeline import SecureRAGPipeline

load_dotenv()

# 1. Create a tiny evaluation dataset
eval_data = {
    "question": [
        "How long must customer data be retained?",
        "Who can access customer data?"
    ],
    "ground_truth": [
        "Customer data must be retained for a minimum of 3 years and a maximum of 7 years.",
        "Access is restricted to authorized personnel only."
    ]
}

# 2. Run each question through your RAG pipeline to get answers and contexts
pipeline = SecureRAGPipeline()
answers = []
contexts = []

for q in eval_data["question"]:
    # We need the raw retrieved documents, not just the final answer
    retrieved_docs = pipeline.retriever.get_relevant_documents(q)
    contexts.append([doc.page_content for doc in retrieved_docs])
    answers.append(pipeline.query(q))

# Add the generated answers and contexts to the dataset
eval_data["answer"] = answers
eval_data["contexts"] = contexts

dataset = Dataset.from_dict(eval_data)

# 3. Run RAGAS evaluation
results = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision]
)

print(results)
