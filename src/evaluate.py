"""RAGAS evaluation of the guarded RAG pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from src.config import get_settings
from src.hybrid_retriever import build_hybrid_retriever
from src.logger import get_logger
from src.rag_pipeline import build_rag_chain

log = get_logger("evaluate")

EVAL_SET = {
    "question": [
        "How long must customer data be retained?",
        "Who can access customer data?",
        "What should happen if a data breach is suspected?",
    ],
    "ground_truth": [
        "Customer data must be retained for a minimum of 3 years and a maximum of 7 years.",
        "Access to customer data is restricted to authorized personnel only.",
        "Any suspected data breach must be reported to the security team within 24 hours.",
    ],
}


def run_evaluation(output_path: str | None = None) -> dict:
    """Run RAGAS metrics and return/save the result dict."""
    settings = get_settings()
    log.info("Starting RAGAS evaluation")

    retriever = build_hybrid_retriever()
    chain = build_rag_chain()

    answers: list[str] = []
    contexts: list[list[str]] = []

    for q in EVAL_SET["question"]:
        log.info(f"Evaluating: {q}")
        docs = retriever.invoke(q)
        contexts.append([d.page_content for d in docs])
        answers.append(chain.invoke(q))

    data = {
        **EVAL_SET,
        "answer": answers,
        "contexts": contexts,
    }
    dataset = Dataset.from_dict(data)

    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )

    scores = {k: float(v) for k, v in result.items() if isinstance(v, (int, float))}
    log.success(f"RAGAS scores: {scores}")

    out = Path(output_path or "evaluation_results.json")
    out.write_text(json.dumps(scores, indent=2), encoding="utf-8")
    log.info(f"Saved evaluation results to {out}")

    return scores


if __name__ == "__main__":
    run_evaluation()
